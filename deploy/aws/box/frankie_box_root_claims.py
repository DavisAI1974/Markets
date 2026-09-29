"""One ROOT per day, claimed once (Greg, 2026-09-29: the Pods and the boxes share one queue of ready days; "never two
ROOTs of the same day": duplicate data declines a run). SPEC-pod-day-runner.md, "The claim".

The claim store lives on the main box, /opt/frankie-box/work/root-claims/<run>/<day>.json, one file per day, created
with O_CREAT|O_EXCL (atomic on one filesystem: exactly one creator wins). Every runner of a day's ROOT takes the claim
BEFORE it starts and nobody starts without it:
  the main box's orchestrator (frankie_box_experiment.py, stage root) takes it locally, where = box:<host>;
  a Pod or a worker box takes it through the runner's SSM call of frankie_box_pod_root.sh ACTION=claim on the main box,
  where = pod:<id> or worker:<instance>.
A claim holds {day, run, where, started, attempt (the ROOT directory name it will write), commit}. Finished: <day>.done.json
is written beside it (the claim stays, so the day is never claimed again). Failed or lost: the claim is RENAMED to
<day>.released-<utc>-<n>.json with the reason (never deleted: the evidence stays) and the day may be claimed again.
The store is opt-in: while /opt/frankie-box/work/root-claims does not exist, active() is False and the orchestrator
behaves exactly as before (no claim taken or checked).
"""
import json
import os
import socket
import time
from pathlib import Path

CLAIMS = Path('/opt/frankie-box/work/root-claims')
SCHEMA = 'FRANKIE_ROOT_CLAIM_V1'


def active():
    return CLAIMS.is_dir()


def enable():
    CLAIMS.mkdir(parents=True, exist_ok=True)


def this_box():
    """box:<instance id or host name>, the orchestrator's own 'where'."""
    try:
        return 'box:' + Path('/var/lib/cloud/data/instance-id').read_text().strip()
    except OSError:
        return 'box:' + socket.gethostname()


def _path(run, day):
    if not (run and all(c.isalnum() or c in '_-' for c in run) and len(day) == 8 and day.isdigit()):
        raise ValueError('run [A-Za-z0-9_-] and day YYYYMMDD required')
    return CLAIMS / run / ('%s.json' % day)


def _write_new(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(json.dumps(doc, indent=1, sort_keys=True) + '\n')
        f.flush()
        os.fsync(f.fileno())
    dfd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def holder(run, day):
    """The claim document, or None when the day is unclaimed (or its last claim was released)."""
    path = _path(run, day)
    try:
        doc = json.loads(path.read_bytes())
    except FileNotFoundError:
        return None
    done = path.with_name('%s.done.json' % day)
    if done.is_file():
        doc = dict(doc, done=json.loads(done.read_bytes()))
    return doc


def claim(run, day, where, attempt, commit=None, **extra):
    """(True, claim) when this call created the claim; (False, the holder's claim) when the day is already claimed."""
    path = _path(run, day)
    doc = dict(schema=SCHEMA, run=run, day=day, where=where, attempt=attempt, commit=commit, started=time.time(),
               started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), pid=os.getpid(), **extra)
    try:
        _write_new(path, doc)
    except FileExistsError:
        return False, holder(run, day)
    return True, doc


def release(run, day, reason, by, expect_where=None, expect_attempt=None):
    """Move the day's claim aside (renamed, never deleted) so the day can be claimed again. Refused when the claim is
    done, or held by someone other than expect_where / for another attempt than expect_attempt."""
    path = _path(run, day)
    doc = holder(run, day)
    if doc is None:
        return False, 'no claim for %s %s' % (run, day)
    if doc.get('done'):
        return False, 'the claim is done (%s): a finished ROOT is never released' % doc['done'].get('calculations')
    if expect_where and doc.get('where') != expect_where:
        return False, 'the claim is held by %s, not %s' % (doc.get('where'), expect_where)
    if expect_attempt and doc.get('attempt') != expect_attempt:
        return False, 'the claim is for attempt %s, not %s' % (doc.get('attempt'), expect_attempt)
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    n = 1
    while True:
        target = path.with_name('%s.released-%s-%d.json' % (day, stamp, n))
        if not target.exists():
            break
        n += 1
    os.rename(path, target)
    _write_new(target.with_name(target.stem + '.reason.json'),
               dict(schema=SCHEMA + '_RELEASE', run=run, day=day, released_by=by, reason=reason, at=time.time(),
                    claim=doc))
    return True, str(target)


def done(run, day, where, attempt, calculations, receipt_sha256, **extra):
    """Mark the day's claim finished (create-only <day>.done.json beside it)."""
    path = _path(run, day)
    doc = holder(run, day)
    if doc is None or doc.get('where') != where or doc.get('attempt') != attempt:
        return False, 'the claim is not held by %s for %s (%s)' % (where, attempt, doc and doc.get('where'))
    try:
        _write_new(path.with_name('%s.done.json' % day),
                   dict(schema=SCHEMA + '_DONE', run=run, day=day, where=where, attempt=attempt, calculations=str(calculations),
                        receipt_sha256=receipt_sha256, at=time.time(), **extra))
    except FileExistsError:
        return False, 'already done'
    return True, None


def listing(run=None):
    """Every claim of a run (or of every run): open, done and released, for status and reconciliation."""
    out = []
    for p in sorted(CLAIMS.glob('%s/*.json' % (run or '*'))) if CLAIMS.is_dir() else ():
        name = p.name
        if name.endswith('.done.json') or name.endswith('.reason.json'):
            continue
        try:
            doc = json.loads(p.read_bytes())
        except (OSError, ValueError):
            continue
        state = 'released' if '.released-' in name else 'claimed'
        if state == 'claimed' and p.with_name('%s.done.json' % doc.get('day')).is_file():
            state = 'done'
        out.append(dict(file=str(p), state=state, **{k: doc.get(k) for k in ('run', 'day', 'where', 'attempt', 'started_utc', 'commit')}))
    return out


def root_running(day):
    """True when a frankie_box_experiment_root.py process for this day runs on this machine (/proc scan)."""
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            argv = (proc / 'cmdline').read_bytes().split(b'\0')
        except OSError:
            continue
        if any(a.endswith(b'frankie_box_experiment_root.py') for a in argv) and day.encode() in argv:
            return True
    return False
