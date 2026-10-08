"""The fleet contract: the shared day list on S3 and the cross-box classroom claim (Greg's fleet plan, 2026-10-08:
"(15) 64 gpu boxes ... 2 days per box ... root ... in parallel all 15 boxes and then first box pair to finish is first
in line to move to classroom because we decided this should be one day at a time").

WHAT THIS ADDS and WHAT IT LEAVES ALONE. ROOT is day-independent (each day reads its own partitions and writes its own
ledgers, sharing nothing until the classroom), so N boxes run ROOT in parallel with no coordination. Knowledge flows
only in the classroom chain, and Greg keeps that strictly serial: one classroom day across the whole fleet at a time.
This module is exactly that serialisation and nothing else:
  - a DAY LIST object on S3 (the 30 days, each with its assigned box and per-stage state) that an operator or the
    fleet-launch step seeds once;
  - a per-day CLAIM record written by an S3 CONDITIONAL WRITE (PutObject If-None-Match: *), so two boxes can never both
    run the same day;
  - ONE global CLASSROOM LEASE (claimed by the same conditional write, holder + day + heartbeat recorded, released by
    the holder at the day's classroom end; a stale lease is taken over ONLY by an explicit operator action, recorded,
    never automatically);
  - an ordered WAITING queue of boxes ready for the classroom, keyed by ROOT-finish time, so the first box to finish is
    first in line.
The stage handoff (frankie_box_stage_handoff.py) calls `classroom_gate` at the ROOT->classroom boundary (the gate
stage, default `teacher`): it claims the lease or, when another box holds it, saves the day and starts a detached WAIT
unit that resumes it when the lease frees. At the classroom boundary it calls `release_if_held`. Every claim, wait and
release lands on the day's handoff receipts, like the existing digest WAIT.

THE SWITCH. The whole module is inert unless the run setting FRANKIE_FLEET_DAY_LIST is set (bucket + key prefix; the
bucket defaults to the frankie granite bucket). When it is UNSET, `enabled()` is False, the handoff takes none of the
fleet branches, and the one-box end-to-end run is byte-for-byte what it was: the existing same-box trigger stays the
default. Knowledge sharing is unchanged either way (all 30 days share completed knowledge; only the classroom chain is
serial).

S3 USAGE. boto3 is imported inside the calls that use it (standard library only at import, exactly as
frankie_box_s3_transport does), so a dispatched checkout can import this without boto3 present. The box uses its own
instance role; this is source and makes no S3 call under a toy. A file-backed fake store (FRANKIE_FLEET_S3_FAKE=<dir>,
atomic create via O_EXCL = the conditional write's semantics) lets the toys race a real claim with no AWS.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# ----------------------------------------------------------------------------------------------- settings & schemas
DAY_LIST_SETTING = 'FRANKIE_FLEET_DAY_LIST'          # the enable switch AND the location (bucket/prefix)
BUCKET_SETTING = 'FRANKIE_FLEET_BUCKET'              # optional bucket override (prefix then lives in DAY_LIST_SETTING)
REGION_SETTING = 'FRANKIE_FLEET_REGION'
INSTANCE_SETTING = 'FRANKIE_FLEET_INSTANCE'          # this box's instance id (user-data sets it from IMDS; toys set it)
FAKE_SETTING = 'FRANKIE_FLEET_S3_FAKE'               # a directory = the file-backed fake store (toys; no boto3, no S3)
GATE_STAGES_SETTING = 'FRANKIE_FLEET_CLASSROOM_GATE_STAGES'   # the stage(s) after which the classroom runs
POLL_SETTING = 'FRANKIE_FLEET_LEASE_POLL_SECONDS'
WAIT_MAX_SETTING = 'FRANKIE_FLEET_WAIT_SECONDS'
FAIR_WAIT_SETTING = 'FRANKIE_FLEET_LEASE_FAIR_WAIT_SECONDS'
PYTHON_SETTING = 'FRANKIE_FLEET_PYTHON'

DEFAULT_BUCKET = 'frankie-granite42-568968024170-us-east-1'   # the frankie leases/pod-root bucket (us-east-1)
DEFAULT_REGION = 'us-east-1'
DEFAULT_GATE_STAGES = ('teacher',)                   # ROOT -> teacher -> (gate) -> classroom; the serial boundary
RELEASE_STAGES = ('classroom', 'data')               # release the lease once the classroom is done (data = safety)
# A day does NOT end at the classroom (Greg, 2026-10-08): after the classroom the day runs data/search ->
# scientific-teacher -> the Granite "voice" meeting -> jev -> end/record/retain, per-box on the grown 64 lane (the
# lease is already released). A day is DONE only at its tail (jev); recording every stage lets the status probe show
# the real current stage and never call a day done at the classroom.
FLEET_DONE_STAGES = ('jev',)
DEFAULT_POLL_SECONDS = 30
DEFAULT_WAIT_SECONDS = 86400                          # the WAIT unit's own life: a whole fleet run
DEFAULT_FAIR_WAIT_SECONDS = 300                       # yield to a strictly earlier LIVE waiter this long, then race
VENV_PYTHON = '/opt/frankie-box/venv/bin/python'

DAY_LIST_SCHEMA = 'FRANKIE_FLEET_DAY_LIST_V1'
CLAIM_SCHEMA = 'FRANKIE_FLEET_CLAIM_V1'
LEASE_SCHEMA = 'FRANKIE_FLEET_LEASE_V1'
WAIT_SCHEMA = 'FRANKIE_FLEET_WAIT_V1'
GATE_SCHEMA = 'FRANKIE_FLEET_GATE_V1'
TAKEOVER_SCHEMA = 'FRANKIE_FLEET_TAKEOVER_V1'

DAY_LIST_KEY = 'day-list.json'
LEASE_KEY = 'classroom.lease.json'


def _utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _try(thunk, default=None):
    """Run a best-effort S3 read/write; never let an advisory call (day-list state, queue read) crash the gate."""
    try:
        return thunk()
    except Exception:  # noqa: BLE001
        return default


# ----------------------------------------------------------------------------------------------- configuration
def enabled():
    """Fleet mode is on exactly when the run setting FRANKIE_FLEET_DAY_LIST is set and non-empty."""
    return bool((os.environ.get(DAY_LIST_SETTING) or '').strip())


def _looks_like_bucket(name):
    import re
    return bool(re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', name)) and ('-' in name or '.' in name)


def location():
    """(bucket, prefix, region). FRANKIE_FLEET_DAY_LIST = `[<bucket>/]<key-prefix>` (an optional s3:// is stripped):
    if it has a '/' and the head looks like a bucket, that head is the bucket and the tail the prefix; otherwise the
    whole value is the prefix under the default (or FRANKIE_FLEET_BUCKET) bucket."""
    raw = (os.environ.get(DAY_LIST_SETTING) or '').strip()
    if raw.startswith('s3://'):
        raw = raw[len('s3://'):]
    raw = raw.strip('/')
    bucket_override = (os.environ.get(BUCKET_SETTING) or '').strip()
    if bucket_override:
        bucket, prefix = bucket_override, raw
    elif '/' in raw and _looks_like_bucket(raw.split('/', 1)[0]):
        bucket, prefix = raw.split('/', 1)
    else:
        bucket, prefix = DEFAULT_BUCKET, raw
    region = (os.environ.get(REGION_SETTING) or DEFAULT_REGION).strip()
    return bucket, prefix.strip('/'), region


def gate_stages():
    raw = (os.environ.get(GATE_STAGES_SETTING) or '').strip()
    return tuple(s for s in raw.split(',') if s) if raw else DEFAULT_GATE_STAGES


def _int_setting(name, default):
    try:
        return int(os.environ.get(name) or default)
    except ValueError:
        return default


def _imds(path):
    """One IMDSv2 GET, or None off-box / on error (never raises)."""
    try:
        import urllib.request
        token = urllib.request.Request('http://169.254.169.254/latest/api/token', method='PUT',
                                       headers={'X-aws-ec2-metadata-token-ttl-seconds': '60'})
        tok = urllib.request.urlopen(token, timeout=1).read().decode()
        req = urllib.request.Request('http://169.254.169.254/latest/' + path,
                                     headers={'X-aws-ec2-metadata-token': tok})
        return urllib.request.urlopen(req, timeout=1).read().decode().strip()
    except Exception:  # noqa: BLE001
        return None


def instance_id():
    """This box's EC2 instance id: FRANKIE_FLEET_INSTANCE (set by user-data from IMDS; toys set it), else IMDSv2, else
    the hostname (never an AWS call under a toy, which always sets the env)."""
    forced = (os.environ.get(INSTANCE_SETTING) or '').strip()
    if forced:
        return forced
    return _imds('meta-data/instance-id') or socket.gethostname()


def classroom_eligible():
    """May this box ever hold the classroom lease? Decision 2 (Greg, "best for science and speed"): a Spot box is NOT
    classroom-eligible (a reclaimed classroom loses a day of the serial chain), so it is REFUSED the lease and its day
    stays at the gate for an operator. Read from FRANKIE_FLEET_CLASSROOM_ELIGIBLE (toys / override) then the box's
    ClassroomEligible instance tag; the default is eligible (a plain On-Demand box with no such tag)."""
    env = (os.environ.get('FRANKIE_FLEET_CLASSROOM_ELIGIBLE') or '').strip().lower()
    if env:
        return env not in ('false', '0', 'no', 'off')
    tag = _imds('meta-data/tags/instance/ClassroomEligible')
    return (tag or 'true').strip().lower() not in ('false', '0', 'no', 'off')


# ----------------------------------------------------------------------------------------------- the S3 store
class ConditionalExists(Exception):
    """put_if_absent lost: the object already exists (S3 PreconditionFailed / the fake's O_EXCL)."""


class FakeStore:
    """A file-backed stand-in for the S3 control plane, used by the toys and whenever FRANKIE_FLEET_S3_FAKE is set.
    put_if_absent is os.open(O_CREAT|O_EXCL): the same all-or-nothing create that PutObject If-None-Match: * gives, so
    two racers (threads or processes) that both call it see exactly one win. No boto3, no network."""

    def __init__(self, bucket, prefix, root):
        self.bucket, self.prefix = bucket, prefix
        self.root = Path(root) / bucket / (prefix or '_')

    def _path(self, key):
        return self.root / key

    def put_if_absent(self, key, body):
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = (json.dumps(body, sort_keys=True, indent=1) + '\n').encode()
        # write the full content to a unique temp, then os.link it into place: link is atomic and fails if the target
        # exists (the exclusivity of If-None-Match: *), and the linked inode already carries the bytes, so a concurrent
        # reader never sees a half-written object (S3's all-or-nothing object visibility). Toy fidelity: without this a
        # racer can read the just-created but still-empty file.
        import uuid
        tmp = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
        tmp.write_bytes(data)
        try:
            os.link(str(tmp), str(path))     # atomic, exclusive; the inode already holds the bytes
        except FileExistsError:
            raise ConditionalExists(key)
        finally:
            try:
                os.remove(str(tmp))
            except FileNotFoundError:
                pass
        return True

    def put(self, key, body):
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        pending = path.with_name(path.name + '.pending-%d' % os.getpid())
        pending.write_bytes((json.dumps(body, sort_keys=True, indent=1) + '\n').encode())
        os.replace(pending, path)
        return True

    def get(self, key):
        try:
            return json.loads(self._path(key).read_bytes())
        except (OSError, ValueError):
            return None

    def head(self, key):
        path = self._path(key)
        return dict(exists=True, bytes=path.stat().st_size, mtime=path.stat().st_mtime) if path.is_file() else None

    def delete(self, key):
        try:
            os.remove(str(self._path(key)))
            return True
        except FileNotFoundError:
            return False

    def list(self, key_prefix):
        base = self._path(key_prefix)
        root = base if base.is_dir() else base.parent
        if not root.is_dir():
            return []
        out = []
        for path in sorted(root.rglob('*')):
            if path.is_file():
                rel = str(path.relative_to(self.root))
                if rel.startswith(key_prefix):
                    out.append(dict(key=rel, bytes=path.stat().st_size, mtime=path.stat().st_mtime))
        return out


class S3Store:
    """The real store: one boto3 S3 client, keys written under the configured prefix. put_if_absent uses PutObject
    with IfNoneMatch='*' (S3 returns 412 PreconditionFailed when the object already exists)."""

    def __init__(self, bucket, prefix, region):
        self.bucket, self.prefix, self.region = bucket, prefix, region
        self._client = None

    def client(self):
        if self._client is None:
            import boto3  # imported here so import of this module never needs boto3
            self._client = boto3.client('s3', region_name=self.region)
        return self._client

    def _key(self, key):
        return '%s/%s' % (self.prefix, key) if self.prefix else key

    def put_if_absent(self, key, body):
        from botocore.exceptions import ClientError
        data = (json.dumps(body, sort_keys=True, indent=1) + '\n').encode()
        try:
            self.client().put_object(Bucket=self.bucket, Key=self._key(key), Body=data,
                                     ContentType='application/json', IfNoneMatch='*')
            return True
        except ClientError as error:
            code = error.response.get('Error', {}).get('Code')
            if code in ('PreconditionFailed', '412', 'ConditionalRequestConflict'):
                raise ConditionalExists(key)
            raise

    def put(self, key, body):
        data = (json.dumps(body, sort_keys=True, indent=1) + '\n').encode()
        self.client().put_object(Bucket=self.bucket, Key=self._key(key), Body=data, ContentType='application/json')
        return True

    def get(self, key):
        from botocore.exceptions import ClientError
        try:
            obj = self.client().get_object(Bucket=self.bucket, Key=self._key(key))
            return json.loads(obj['Body'].read())
        except ClientError as error:
            if error.response.get('Error', {}).get('Code') in ('NoSuchKey', 'NoSuchBucket', '404'):
                return None
            raise
        except ValueError:
            return None

    def head(self, key):
        from botocore.exceptions import ClientError
        try:
            obj = self.client().head_object(Bucket=self.bucket, Key=self._key(key))
            return dict(exists=True, bytes=obj.get('ContentLength'), mtime=obj.get('LastModified'))
        except ClientError as error:
            if error.response.get('Error', {}).get('Code') in ('404', 'NoSuchKey', 'NotFound'):
                return None
            raise

    def delete(self, key):
        self.client().delete_object(Bucket=self.bucket, Key=self._key(key))
        return True

    def list(self, key_prefix):
        full = self._key(key_prefix)
        out, token = [], None
        while True:
            kw = dict(Bucket=self.bucket, Prefix=full)
            if token:
                kw['ContinuationToken'] = token
            resp = self.client().list_objects_v2(**kw)
            for item in resp.get('Contents', []):
                rel = item['Key'][len(self.prefix) + 1:] if self.prefix else item['Key']
                out.append(dict(key=rel, bytes=item.get('Size'), mtime=item.get('LastModified')))
            if not resp.get('IsTruncated'):
                return out
            token = resp.get('NextContinuationToken')


def store():
    """The store for this process: the file-backed fake when FRANKIE_FLEET_S3_FAKE is set, else the real S3 store."""
    bucket, prefix, region = location()
    fake = (os.environ.get(FAKE_SETTING) or '').strip()
    if fake:
        return FakeStore(bucket, prefix, fake)
    return S3Store(bucket, prefix, region)


# ----------------------------------------------------------------------------------------------- keys
def claim_key(run, day, stage):
    return 'claims/%s/%s/%s.json' % (run, day, stage)


def waiting_key(run, day):
    return 'waiting/%s/%s.json' % (run, day)


# ----------------------------------------------------------------------------------------------- the day list
def read_day_list(st=None):
    return (st or store()).get(DAY_LIST_KEY)


def seed_day_list(run, assignments, commit, *, st=None):
    """Write the day list once (create-only): the 30 days with their assigned box and an empty per-stage state. A list
    that already exists is returned unchanged (idempotent, two seeders safe). `assignments` = [{day, box[, spot]}]."""
    st = st or store()
    body = dict(schema=DAY_LIST_SCHEMA, run=run, created_utc=_utc(), commit=commit,
                days=[dict(day=a['day'], box=a.get('box'), spot=bool(a.get('spot')), stages={}) for a in assignments])
    try:
        st.put_if_absent(DAY_LIST_KEY, body)
        return dict(status='seeded', days=len(body['days']), day_list=body)
    except ConditionalExists:
        return dict(status='exists', day_list=read_day_list(st))


def record_stage_progress(run, day, stage, *, st=None, instance=None):
    """Record a stage DONE on the shared day list and advance current_stage; set done_utc only at the tail stage (jev).
    The day is carried through its FULL sequence (classroom is not the end), so the status probe shows the real current
    stage and marks a day done only after jev/end. Advisory (unconditional read-modify-write); the lease and the claim
    stay the authoritative control objects."""
    st = st or store()
    instance = instance or instance_id()
    doc = st.get(DAY_LIST_KEY)
    if not doc:
        return dict(status='no_list')
    for entry in doc.get('days', []):
        if entry.get('day') == day:
            entry.setdefault('stages', {})[stage] = dict(state='done', at=_utc(), instance=instance)
            entry['current_stage'] = stage
            if stage in FLEET_DONE_STAGES:
                entry['done_utc'] = _utc()
            st.put(DAY_LIST_KEY, doc)
            return dict(status='recorded', day=day, stage=stage, done=stage in FLEET_DONE_STAGES)
    return dict(status='day_absent', day=day)


def set_day_stage_state(run, day, stage, state, *, st=None):
    """Advisory: record a day's per-stage state on the shared list (read-modify-write, unconditional put). The claim
    record and the lease are the authoritative control objects; this keeps the human-readable list current."""
    st = st or store()
    doc = st.get(DAY_LIST_KEY)
    if not doc:
        return dict(status='no_list')
    for entry in doc.get('days', []):
        if entry.get('day') == day:
            entry.setdefault('stages', {})[stage] = dict(state=state, at=_utc(), instance=instance_id())
            st.put(DAY_LIST_KEY, doc)
            return dict(status='set', day=day, stage=stage, state=state)
    return dict(status='day_absent', day=day)


# ----------------------------------------------------------------------------------------------- per-day claim
def claim_day(run, day, stage, commit, *, st=None, instance=None):
    """Claim a (run, day, stage) with a conditional write: exactly one box can win. Returns {won, holder, record}.
    The days are pre-assigned on the list; this is the hard guarantee that two boxes never run the same day."""
    st = st or store()
    instance = instance or instance_id()
    key = claim_key(run, day, stage)
    body = dict(schema=CLAIM_SCHEMA, run=run, day=day, stage=stage, instance=instance, commit=commit, claimed_utc=_utc())
    try:
        st.put_if_absent(key, body)
        return dict(won=True, holder=instance, record=body, key=key)
    except ConditionalExists:
        held = st.get(key) or {}
        return dict(won=(held.get('instance') == instance), holder=held.get('instance'), record=held, key=key,
                    reason='already claimed by %s' % held.get('instance'))


# ----------------------------------------------------------------------------------------------- waiting queue
def record_root_finished(run, day, *, st=None, instance=None, epoch=None):
    """Write this box's waiting marker (create-only): it is ready for the classroom. The epoch (ROOT/teacher finish
    time) orders the queue. A marker that stands is kept (the first finish time is the one that orders)."""
    st = st or store()
    instance = instance or instance_id()
    epoch = time.time() if epoch is None else epoch
    body = dict(schema=WAIT_SCHEMA, run=run, day=day, instance=instance, root_finish_epoch=round(epoch, 3),
                root_finished_utc=_utc())
    try:
        st.put_if_absent(waiting_key(run, day), body)
        return dict(status='recorded', marker=body)
    except ConditionalExists:
        return dict(status='stood', marker=st.get(waiting_key(run, day)))


def waiting_queue(*, st=None):
    """Every waiting marker, ordered by ROOT-finish epoch then day: the line for the classroom."""
    st = st or store()
    markers = []
    for item in st.list('waiting/'):
        doc = st.get(item['key'])
        if doc and doc.get('schema') == WAIT_SCHEMA:
            markers.append(doc)
    markers.sort(key=lambda m: (m.get('root_finish_epoch', 0), m.get('day', '')))
    return markers


def next_in_line(*, st=None):
    """The earliest waiting marker (first ROOT to finish is first in line), or None when the queue is empty."""
    queue = waiting_queue(st=st)
    return queue[0] if queue else None


# ----------------------------------------------------------------------------------------------- classroom lease
def lease_holder(*, st=None):
    return (st or store()).get(LEASE_KEY)


def acquire_classroom_lease(run, day, commit, *, st=None, instance=None, fair=True, fair_wait=None):
    """Try to take the ONE global classroom lease for (run, day). Returns {acquired, holder, reason}.
    - Idempotent: if this box already holds it, acquired is True with no write.
    - Held by another box: acquired False (the caller waits).
    - Free: when `fair`, yield to a strictly earlier LIVE waiter (its marker younger than fair_wait) so the first box
      to finish goes first; a stale earlier waiter never deadlocks the line (after fair_wait we race anyway). The take
      itself is a conditional write, so even in a tie exactly one box wins."""
    st = st or store()
    instance = instance or instance_id()
    fair_wait = _int_setting(FAIR_WAIT_SETTING, DEFAULT_FAIR_WAIT_SECONDS) if fair_wait is None else fair_wait
    cur = lease_holder(st=st)
    if cur and cur.get('holder_instance') == instance and cur.get('run') == run and cur.get('day') == day:
        return dict(acquired=True, holder=instance, reason='already held by this box', lease=cur)
    if cur:
        return dict(acquired=False, holder=cur.get('holder_instance'), reason='held by %s for %s/%s'
                    % (cur.get('holder_instance'), cur.get('run'), cur.get('day')), lease=cur)
    if fair:
        earliest = next_in_line(st=st)
        if earliest and not (earliest.get('run') == run and earliest.get('day') == day):
            head = st.head(waiting_key(earliest.get('run'), earliest.get('day')))
            age = (time.time() - head['mtime']) if head and isinstance(head.get('mtime'), (int, float)) else 0.0
            if age < fair_wait:
                return dict(acquired=False, holder=None, reason='yielding to earlier waiter %s (%s/%s), %.0fs old'
                            % (earliest.get('instance'), earliest.get('run'), earliest.get('day'), age),
                            next_in_line=earliest)
    body = dict(schema=LEASE_SCHEMA, holder_instance=instance, run=run, day=day, commit=commit,
                acquired_utc=_utc(), heartbeat_utc=_utc(), heartbeat_epoch=round(time.time(), 3))
    try:
        st.put_if_absent(LEASE_KEY, body)
        return dict(acquired=True, holder=instance, reason='acquired', lease=body)
    except ConditionalExists:
        cur = lease_holder(st=st) or {}
        return dict(acquired=False, holder=cur.get('holder_instance'), reason='lost the race to %s'
                    % cur.get('holder_instance'), lease=cur)


def heartbeat_classroom_lease(run, day, *, st=None, instance=None):
    """Refresh the lease heartbeat, only while this box holds it (advisory: a stale lease is NEVER taken over
    automatically; the timestamp is for the operator deciding a takeover)."""
    st = st or store()
    instance = instance or instance_id()
    cur = lease_holder(st=st)
    if not (cur and cur.get('holder_instance') == instance and cur.get('run') == run and cur.get('day') == day):
        return dict(status='not_held', holder=(cur or {}).get('holder_instance'))
    cur['heartbeat_utc'], cur['heartbeat_epoch'] = _utc(), round(time.time(), 3)
    st.put(LEASE_KEY, cur)
    return dict(status='beat', lease=cur)


def release_classroom_lease(run, day, *, st=None, instance=None):
    """Release the lease at the day's classroom end, only when this box holds it, and drop this box's waiting marker so
    the next box is first in line."""
    st = st or store()
    instance = instance or instance_id()
    cur = lease_holder(st=st)
    held = bool(cur and cur.get('holder_instance') == instance and cur.get('run') == run and cur.get('day') == day)
    released = st.delete(LEASE_KEY) if held else False
    st.delete(waiting_key(run, day))
    return dict(status='released' if released else 'not_held', released=released, run=run, day=day, instance=instance,
                prior_holder=(cur or {}).get('holder_instance'))


def release_if_held(run, day, *, st=None, instance=None, log=print):
    """Idempotent release used by the handoff at the classroom (and, as a safety net, the data) boundary."""
    out = release_classroom_lease(run, day, st=st, instance=instance)
    log('fleet: classroom lease %s for %s/%s' % (out['status'], run, day))
    return out


def takeover_classroom_lease(run, day, commit, by, *, force=False, st=None, instance=None):
    """An operator ONLY: reclaim a stale lease. Refuses without force. Records the old holder and the reason in an
    audit object before overwriting the lease. This is the only path that overrides the conditional write, and it is
    never automatic."""
    st = st or store()
    instance = instance or instance_id()
    cur = lease_holder(st=st)
    if not force:
        return dict(status='refused', reason='a lease takeover is an explicit operator action: pass force=True',
                    current=cur)
    audit = dict(schema=TAKEOVER_SCHEMA, at=_utc(), by=by, new_holder=instance, run=run, day=day, commit=commit,
                 prior=cur)
    st.put('classroom.lease.takeover-%d.json' % int(time.time()), audit)
    body = dict(schema=LEASE_SCHEMA, holder_instance=instance, run=run, day=day, commit=commit, acquired_utc=_utc(),
                heartbeat_utc=_utc(), heartbeat_epoch=round(time.time(), 3), takeover=audit)
    st.put(LEASE_KEY, body)
    return dict(status='taken_over', lease=body, prior=cur)


# ----------------------------------------------------------------------------------------------- the handoff gate
def _python():
    forced = os.environ.get(PYTHON_SETTING)
    if forced:
        return forced
    return VENV_PYTHON if Path(VENV_PYTHON).is_file() else sys.executable


def classroom_gate(run, day, stage, out_dir, code_root, commit, *, log=print, st=None, start_wait=True):
    """At the ROOT->classroom boundary (the gate stage): record this box ready, then claim the lease. Returns a receipt
    with decision 'proceed' (this box holds the lease; the day goes straight on to the classroom) or 'waiting' (another
    box holds it; the caller saves the day and a detached WAIT unit resumes it when the lease frees). Written to
    <out_dir>/fleet-gate.json."""
    st = st or store()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    instance = instance_id()
    if not classroom_eligible():
        # decision 2: a Spot (ClassroomEligible=false) box must NEVER hold the classroom lease; it refuses here and the
        # day stays at the gate (saved) for an operator to move its ROOT/teacher output to an On-Demand box. No lease,
        # no WAIT unit (a WAIT unit would eventually acquire the lease, which is exactly what must not happen).
        rec = dict(schema=GATE_SCHEMA, run=run, day=day, stage=stage, instance=instance, commit=commit, at=time.time(),
                   decision='ineligible', holder=None,
                   reason='this box is ClassroomEligible=false (Spot / ROOT-stage only); it is refused the classroom '
                          'lease. The day stays saved at the gate for an operator to run its classroom on an '
                          'On-Demand box.')
        _try(lambda: set_day_stage_state(run, day, 'classroom', 'ineligible', st=st))
        _write_json(out_dir / 'fleet-gate.json', rec)
        log('fleet gate %s %s/%s: ineligible (%s)' % (stage, run, day, rec['reason']))
        return rec
    try:
        ready = record_root_finished(run, day, st=st, instance=instance)
        got = acquire_classroom_lease(run, day, commit, st=st, instance=instance)
    except Exception as error:  # noqa: BLE001 - an S3 error is a WAIT (fail-closed: never two classrooms), not a crash;
        # the WAIT unit retries S3 every poll, so a transient blip recovers on its own
        ready = dict(status='error', error='%s: %s' % (type(error).__name__, str(error)[:200]))
        got = dict(acquired=False, holder=None, reason='fleet store error: %s: %s' % (type(error).__name__, str(error)[:200]))
    base = dict(schema=GATE_SCHEMA, run=run, day=day, stage=stage, instance=instance, commit=commit, at=time.time(),
                ready=ready, lease=got)
    if got['acquired']:
        _try(lambda: set_day_stage_state(run, day, 'classroom', 'lease_held', st=st))
        rec = dict(base, decision='proceed', reason='this box holds the global classroom lease; straight on to the '
                                                    'classroom (no save at the gate in fleet mode)')
    else:
        queue = _try(lambda: waiting_queue(st=st)) or []
        position = next((i for i, m in enumerate(queue) if m.get('run') == run and m.get('day') == day), None)
        rec = dict(base, decision='waiting', holder=got.get('holder'), position=position, queue_len=len(queue),
                   reason='the global classroom lease is held by %s; %s/%s is #%s in line; the day is saved and a WAIT '
                          'unit will resume it when the lease frees' % (got.get('holder'), run, day, position))
        _try(lambda: set_day_stage_state(run, day, 'classroom', 'waiting', st=st))
        if start_wait:
            rec['wait_unit'] = start_wait_unit(run, day, stage, out_dir, code_root, commit, log=log)
    _write_json(out_dir / 'fleet-gate.json', rec)
    log('fleet gate %s %s/%s: %s (%s)' % (stage, run, day, rec['decision'], rec['reason']))
    return rec


def start_wait_unit(run, day, stage, out_dir, code_root, commit, *, log=print):
    """Start the detached WAIT unit once (guarded by fleet-wait.started, create-only). The unit polls the lease and,
    when it acquires it, resumes + kicks the day on the launching checkout; it never cleans or kills anything."""
    import shutil
    out_dir = Path(out_dir)
    if (os.environ.get('FRANKIE_FLEET_NO_WAIT_UNIT') or '').strip():
        # gate-only mode (and the toys): do not spawn the detached poller; the day stays saved and a re-dispatch or an
        # operator re-runs the gate. Recorded so the receipt is honest about why no poller exists.
        return dict(status='suppressed', reason='FRANKIE_FLEET_NO_WAIT_UNIT set: no WAIT unit spawned')
    started = out_dir / 'fleet-wait.started'
    try:
        with open(started, 'x', encoding='utf-8') as handle:
            handle.write('%s %s %s %s\n' % (_utc(), run, day, stage))
    except FileExistsError:
        return dict(status='already_started', note='a WAIT unit was started for this boundary before')
    log_path = out_dir / 'fleet-wait.log'
    argv = [_python(), '-B', str(HERE / 'frankie_box_fleet.py'), '--action', 'wait', '--run', run, '--day', day,
            '--stage', stage, '--out-dir', str(out_dir), '--code-root', str(code_root), '--commit', commit]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(code_root))
    how = None
    if shutil.which('systemd-run') and os.environ.get('FRANKIE_HANDOFF_DETACH', 'systemd') != 'session':
        unit = 'frankie-fleet-wait-%s-%s-%d' % (run, day, int(time.time()))
        cmd = ['systemd-run', '--unit', unit, '--collect', '-p', 'StandardOutput=append:%s' % log_path,
               '-p', 'StandardError=append:%s' % log_path, '-p', 'KillMode=mixed'] + \
              [x for k, v in sorted(env.items()) for x in ('-E', '%s=%s' % (k, v))] + argv
        code = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).returncode
        how = dict(method='systemd-run', unit=unit, exit_code=code)
    if how is None or how.get('exit_code') != 0:
        with open(log_path, 'ab') as out:
            proc = subprocess.Popen(argv, env=env, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    start_new_session=True)
        how = dict(method='new session', pid=proc.pid, systemd_run=how)
    return dict(status='started', how=how, log=str(log_path))


def fleet_resume(run, day, code_root, commit, out_dir, *, log=print):
    """Resume + kick the day on the launching checkout (the same two queue.sh calls the handoff trigger makes), once
    (guarded by fleet-resume.fired). Used by the WAIT unit after it acquires the lease."""
    out_dir = Path(out_dir)
    receipt = out_dir / 'fleet-resume.json'
    fired = out_dir / 'fleet-resume.fired'
    queue_sh = os.environ.get('FRANKIE_QUEUE_SH') or str(Path(code_root) / 'deploy/aws/box/frankie_box_frankie_queue.sh')
    base = dict(schema='FRANKIE_FLEET_RESUME_V1', run=run, day=day, code_root=str(code_root), commit=commit,
                at=time.time(), queue_sh=queue_sh)
    try:
        with open(fired, 'x', encoding='utf-8') as handle:
            handle.write('%s %s %s\n' % (_utc(), run, day))
    except FileExistsError:
        return dict(base, status='already_fired')
    env = dict(os.environ, CODE_ROOT=str(code_root), MARKETS_SHA=commit, RUN=run, DAY=day)
    steps = []
    for action, extra in (('resume', {}), ('kick', dict(LINE='root', SCOPE='%s:%s' % (run, day)))):
        result = subprocess.run([queue_sh], env=dict(env, ACTION=action, **extra), capture_output=True, text=True)
        steps.append(dict(action=action, exit_code=result.returncode, stdout=result.stdout[-4000:],
                          stderr=result.stderr[-2000:]))
        log('fleet resume %s/%s: %s exit %d' % (run, day, action, result.returncode))
        if result.returncode != 0:
            return _write_json(receipt, dict(base, status='failed', steps=steps,
                               reason='%s exited %d; the day stays saved (an operator resumes by hand)'
                                      % (action, result.returncode)))
    return _write_json(receipt, dict(base, status='done', steps=steps,
                       reason='the lease was acquired; resumed and kicked on %s (%s)' % (code_root, commit[:12])))


def wait_action(args):
    """The detached WAIT unit: poll the lease; on acquire, resume + kick; otherwise keep the day saved. Bounded by
    FRANKIE_FLEET_WAIT_SECONDS; exit 0 once resumed, 2 if the wait ran out without the lease."""
    poll = _int_setting(POLL_SETTING, DEFAULT_POLL_SECONDS)
    deadline = time.monotonic() + _int_setting(WAIT_MAX_SETTING, DEFAULT_WAIT_SECONDS)
    say = lambda t: print('%s %s' % (_utc(), t), flush=True)  # noqa: E731
    out_dir = Path(args.out_dir)
    st = store()
    while True:
        got = acquire_classroom_lease(args.run, args.day, args.commit, st=st)
        _write_json(out_dir / 'fleet-gate.json', dict(schema=GATE_SCHEMA, run=args.run, day=args.day, stage=args.stage,
                    instance=instance_id(), decision='proceed' if got['acquired'] else 'waiting', lease=got,
                    at=time.time(), in_wait_unit=True))
        if got['acquired']:
            set_day_stage_state(args.run, args.day, 'classroom', 'lease_held', st=st)
            res = fleet_resume(args.run, args.day, args.code_root, args.commit, out_dir, log=say)
            say('fleet wait: lease acquired; resume %s' % res['status'])
            return 0
        say('fleet wait: %s; next poll in %ds' % (got['reason'], poll))
        if time.monotonic() >= deadline:
            say('fleet wait: ran out of time without the lease; the day stays saved for an operator')
            return 2
        time.sleep(poll)


def _write_json(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.pending')
    pending.write_text(json.dumps(body, indent=1, sort_keys=True, default=str) + '\n', encoding='utf-8')
    os.replace(pending, path)
    return body


# ----------------------------------------------------------------------------------------------- CLI
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n', 1)[0])
    sub = parser.add_subparsers(dest='action', required=True)
    for name in ('status', 'queue'):
        sub.add_parser(name)
    seed = sub.add_parser('seed-day-list')
    seed.add_argument('--run', required=True)
    seed.add_argument('--commit', required=True)
    seed.add_argument('--assignments', required=True, help='JSON list [{"day":"YYYYMMDD","box":"i-..","spot":false}]')
    claim = sub.add_parser('claim-day')
    for flag in ('--run', '--day', '--commit'):
        claim.add_argument(flag, required=True)
    claim.add_argument('--stage', default='root')
    take = sub.add_parser('takeover-lease')
    take.add_argument('--run', required=True)
    take.add_argument('--day', required=True)
    take.add_argument('--commit', required=True)
    take.add_argument('--by', required=True)
    take.add_argument('--force', action='store_true')
    w = sub.add_parser('wait')
    for flag in ('--run', '--day', '--stage', '--out-dir', '--code-root', '--commit'):
        w.add_argument(flag, required=True)
    args = parser.parse_args(argv)
    if args.action == 'wait':
        return wait_action(args)
    if not enabled():
        print('fleet mode is OFF (%s unset): nothing to do' % DAY_LIST_SETTING)
        return 0
    if args.action == 'status':
        print(json.dumps(dict(location=location(), instance=instance_id(), lease=lease_holder(),
                              day_list=read_day_list()), indent=1, default=str))
    elif args.action == 'queue':
        print(json.dumps(waiting_queue(), indent=1, default=str))
    elif args.action == 'claim-day':
        out = claim_day(args.run, args.day, args.stage, args.commit)
        print(json.dumps(out, indent=1, default=str))
        return 0 if out.get('won') else 1
    elif args.action == 'seed-day-list':
        print(json.dumps(seed_day_list(args.run, json.loads(args.assignments), args.commit), indent=1, default=str))
    elif args.action == 'takeover-lease':
        print(json.dumps(takeover_classroom_lease(args.run, args.day, args.commit, args.by, force=args.force),
                         indent=1, default=str))
    return 0


if __name__ == '__main__':
    sys.exit(main())
