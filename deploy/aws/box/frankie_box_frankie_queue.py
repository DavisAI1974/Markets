"""Frankie's FIFO queue: two lines on the box, the ROOT line and the CLASS line, each first in first out.

Greg, 2026-09-29: "I don't want any days dropped and moved forward because he was busy"; "That's fine for the order
fifo"; "I'm saying order by first in the pod first out the pod or box"; "And the root calcs too. Whichever trade date hits
that spot first goes first"; "Class days are sequential. 1st day then 2nd day and so on."

THE ORDER RULE (both lines). A day's place in a line is the moment it ENTERS that line: enqueued_at, then a monotonic
sequence number (seq, assigned under the queue lock, so two runs enqueueing at once get distinct, ordered numbers). Days
leave in exactly that order: first in, first out. Not trading-date order, not plan order, not by run: arrival order only.
Nothing is dropped, nothing is skipped, nothing is reordered. The front of a line is the lowest seq that is not done; an
entry behind a front that is not done waits for it, whatever the front waits on (show lists it waiting_prior, naming the
entry ahead). A failed entry stops its line there (never skipped); the next worker start retries it once.

THE ROOT LINE. A day enters it the moment it is ROOT-ready: its sealed ingest and its day file attached (the orchestrator's
own checks: ingest_of / its ingest receipt and external_ready; frankie_box_experiment.Run.root_enqueue). Trading-date
order does not matter for calculations (the 10th does not need the 9th). Days leave in arrival order to the next free
day-run slot: a box slot (box_slots: EXACTLY 16 CPUs free in the box's CPU booking ledger frankie_box_cores.py, which the
ROOT step then books under taskset; a step that cannot book them waits and keeps its place) or a Pod through
the Pod ROOT loop's claims (/opt/frankie-box/work/root-claims/, frankie_box_root_claims.py; frankie_box_pod_root.py
ACTION=queue lists the line's days in line order and ACTION=claim refuses a day while an earlier entry of the line has not
started: root_gate). One claim per day, never twice. Several ROOTs run at once (one per slot), but they START in line
order; they may finish in any order. A finished ROOT (box or Pod) marks its entry done; an arm day whose teacher rows are
there then enters the CLASS line at once (Run.enqueue_classroom).

THE CLASS LINE. A classroom-arm day enters it the moment its ROOT (with the digest) and its teacher rows are done and its
day file is attached (the classroom step's own checks: Run.classroom_ready). Class days are sequential: EXACTLY ONE CLASS
RUNS AT A TIME (one class worker per box, its own lock; the classroom step itself also holds class-running.lock, so an
orchestrator run with the queue off never runs a class beside it; Pods never run classes). Each class gets a SCHOOL-DAY
NUMBER = its position in the class line in the order classes are taken (1, 2, 3, ...; after the classes already numbered
in the reports index before the line existed: school_day_base, recorded once), never reused, never skipped. The day's
report number N (CLASSROOM / FRANKIE / JEV REPORT #N) IS that school-day number: the worker reserves it in the reports
index (frankie_box_experiment_day_reports.reserve_number(number=N)) when it takes the day, before the classroom runs, so
every later reader (the reports step, the school step, Jev's dispatch) reads the same N; it is in the queue entry, the
step receipts and the school row (<brain>/school/index.json school_day). Class k starts only after class k-1 is done and
carries class k-1's classroom: PREVIOUS = the classroom of the entry that most recently finished class (the last done
entry by completion sequence done_seq), recorded in the entry and in the classroom step's receipt (previous_from). Before
the line has a done entry: the plan's PREVIOUS_CLASSROOM, else the most recently finished complete classroom on the box
(by its completion.json time), recorded as the bootstrap. A previous class of a LATER trading date is carried as ordered
and flagged previous_trade_date_later (the school knowledge base keeps its own trading-date wall: frankie_box_brain.
school_rows before_day; listed, Greg's call).

WHAT THE CLASS WORKER RUNS per day (everything that carries his previous day), in order, through the orchestrator's own
step methods (frankie_box_experiment.Run; nothing re-implemented): classroom, frankie_lessons (the scientific teacher on
the day's own classroom novel findings, R09; the orchestrator's batch lessons leave queued days to the worker), exchange,
voice (not wired: passes as listed), school, reports. Jev's material relay stays the orchestrator's step (a hand-off to
his Pod, never carried into the next class). Receipts per step in the run's own directory
(/opt/frankie-box/work/experiment/<run>/days/<day>/<stage>.json), so a restart resumes exactly: finished steps are skipped.

A DAY THAT WAITS RESUMES BY ITSELF. The worker keeps the front entry and polls it (POLL seconds, default 60) instead of
ending; it never starts a new day or a new poll after its bound (MAX_SECONDS) and then saves the entry back to queued with
the reason (exit 5). Every orchestrator start kicks the workers of both lines (a detached systemd-run unit, bounded the
same way), and so does every enqueue; the worker holds its own lock (a second one exits at once) and releases it while it
still holds the queue lock, so an entry enqueued as it goes idle is always picked up by the next kick.

FILES (/opt/frankie-box/work/frankie-queue/): <line>.json (the line, atomic replace), <line>-events.jsonl (append-only: every
enqueue, refusal, take, poll count, finish, kick), .lock (flock, both lines), <line>-worker.lock, <line>-worker.json (the
worker's state), <line>-worker/progress.json (FRANKIE_WORK_PROBE_V1), logs/<line>-worker.log, class-running.lock.

Actions (frankie_box_frankie_queue.sh ACTION=...): show (read-only: both lines, every entry with its state and reason, the
workers), enqueue (LINE RUN DAY: the orchestrator's readiness checks, then the entry), worker (LINE: runs in the
foreground, bounded by MAX_SECONDS), kick (LINE: starts the detached worker unless one runs). No model call, no Pod call,
no Granite, no Databento.
"""
import argparse
import contextlib
import fcntl
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUEUE = Path('/opt/frankie-box/work/frankie-queue')
SCHEMA = 'FRANKIE_QUEUE_LINE_V1'
LINES = ('root', 'class')
STATES = ('queued', 'running', 'done', 'failed')
CLASS_STAGES = ('classroom', 'frankie_lessons', 'exchange', 'voice', 'school', 'reports')
CORES_PER_SLOT = 16                       # a box day-run slot: exactly 16 booked CPUs (the core ledger's rule)
# the Run settings an entry carries (the enqueuer's orchestrator arguments), so the worker builds the same Run
SETTINGS = dict(ingest_workers=31, parallel_days=4, ingest_mode='sequential', ingest_observation='full',
                ingest_verify='deferred', data_workers=1, search_workers=8, teacher_cpus=0, disk_floor_gb=100.0, lags=20,
                frankie_queue='on', root_queue='on', queue_worker_seconds=43200, queue_poll_seconds=60)


def utc(t=None):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t))


# ------------------------------------------------------------------------------------------------------ the store

@contextlib.contextmanager
def locked():
    """The queue lock (exclusive, both lines): every read-modify-write of a line happens under it."""
    QUEUE.mkdir(parents=True, exist_ok=True)
    with open(QUEUE / '.lock', 'a+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _path(line):
    if line not in LINES:
        raise ValueError('line must be one of %s' % (LINES,))
    return QUEUE / ('%s.json' % line)


def load(line):
    path = _path(line)
    if not path.is_file():
        return dict(schema=SCHEMA, line=line, next_seq=1, next_done_seq=1, entries=[])
    doc = json.loads(path.read_bytes())
    if doc.get('schema') != SCHEMA or doc.get('line') != line:
        raise SystemExit('%s is not a %s %s line; refused' % (path, SCHEMA, line))
    return doc


def save(line, doc):
    path = _path(line)
    tmp = path.with_suffix('.pending')
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(json.dumps(doc, indent=1, sort_keys=True) + '\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def event(line, kind, **fields):
    """One line appended to <line>-events.jsonl (called under the queue lock)."""
    QUEUE.mkdir(parents=True, exist_ok=True)
    body = dict(at=time.time(), utc=utc(), line=line, event=kind, pid=os.getpid(), host=socket.gethostname(), **fields)
    with open(QUEUE / ('%s-events.jsonl' % line), 'a', encoding='utf-8') as f:
        f.write(json.dumps(body, sort_keys=True, default=str) + '\n')


def ordered(doc):
    return sorted(doc['entries'], key=lambda x: x['seq'])


def find(doc, seq):
    return next(x for x in doc['entries'] if x['seq'] == seq)


def front(doc):
    """The lowest-seq entry that is not done (the head of the line), or None."""
    return next((x for x in ordered(doc) if x['state'] != 'done'), None)


def entry_of(line, run, day):
    """The (run, day) entry of a line, read without the lock (the file is replaced atomically), or None."""
    try:
        doc = load(line)
    except (OSError, ValueError):
        return None
    return next((x for x in doc['entries'] if x['run'] == run and x['day'] == day), None)


def enqueue(line, run, day, commit, code_root, plan_sha256, settings, readiness, by):
    """(entry, 'enqueued' | 'existing') or (None, why refused). One entry per (day, run); a day already in the line from
    another run (not failed) is declined: duplicate data (the same day's ROOT or class twice)."""
    with locked():
        doc = load(line)
        for x in doc['entries']:
            if x['run'] == run and x['day'] == day:
                return x, 'existing'
        others = [x for x in doc['entries'] if x['day'] == day and x['state'] != 'failed']
        if others:
            why = ('%s is in the %s line already from run %s (seq %d, %s): duplicate data declines a second entry of the '
                   'day' % (day, line, others[0]['run'], others[0]['seq'], others[0]['state']))
            event(line, 'enqueue_refused', run=run, day=day, reason=why, by=by)
            return None, why
        now = time.time()
        seq = doc['next_seq']
        doc['next_seq'] = seq + 1
        entry = dict(seq=seq, day=day, run=run, enqueued_at=now, enqueued_utc=utc(now), state='queued',
                     reason='in line (seq %d)' % seq, enqueued_by=dict(commit=commit, code_root=str(code_root), by=by,
                                                                      pid=os.getpid(), host=socket.gethostname()),
                     plan_sha256=plan_sha256, settings={k: settings.get(k, v) for k, v in SETTINGS.items()},
                     readiness=readiness, attempts=[], stages={}, receipts=[])
        doc['entries'].append(entry)
        save(line, doc)
        event(line, 'enqueued', seq=seq, run=run, day=day, by=by, readiness=readiness)
        return entry, 'enqueued'


def settings_of(a):
    """The orchestrator arguments an entry carries (defaults for any the Namespace lacks)."""
    return {k: getattr(a, k, v) for k, v in SETTINGS.items()}


# ------------------------------------------------------------------------------------------------------ show

def line_view(doc, line):
    """Every entry in line order with its line state: done, failed, running, queued (next to leave) or waiting_prior
    (behind an entry that has not left the line, named). The class line runs one day at a time, so everything behind its
    first entry that is not done waits for it; the ROOT line runs one day per free slot, so a queued day waits for the
    first entry that has not started (queued or failed)."""
    out, ahead, position = [], None, 0
    for x in ordered(doc):
        position += 1
        v = dict(position=position, seq=x['seq'], day=x['day'], run=x['run'], state=x['state'], reason=x.get('reason'),
                 enqueued_utc=x['enqueued_utc'], attempts=len(x.get('attempts') or []),
                 last_attempt=(x.get('attempts') or [None])[-1], where=x.get('where'), stages=x.get('stages'),
                 done_seq=x.get('done_seq'), done_utc=x.get('done_utc'), school_day=x.get('school_day'),
                 previous=x.get('previous'), classroom=x.get('classroom'), calculations=x.get('calculations'),
                 class_line=x.get('class_line'), readiness=x.get('readiness'), line_state=x['state'])
        if x['state'] == 'queued' and ahead is not None:
            v['line_state'] = 'waiting_prior'
            v['behind'] = 'seq %d day %s run %s (%s) has not left the line' % (ahead['seq'], ahead['day'], ahead['run'],
                                                                              ahead['state'])
        if ahead is None and x['state'] != 'done' and (line == 'class' or x['state'] in ('queued', 'failed')):
            ahead = x
        out.append(v)
    return out


def worker_state(line):
    """(the worker's last written state, whether its lock is held right now); read-only (no file is created)."""
    status = None
    path = QUEUE / ('%s-worker.json' % line)
    if path.is_file():
        try:
            status = json.loads(path.read_bytes())
        except ValueError:
            status = dict(unreadable=str(path))
    held = None
    lock = QUEUE / ('%s-worker.lock' % line)
    if lock.is_file():
        fd = os.open(lock, os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            held = False
        except BlockingIOError:
            held = True
        finally:
            os.close(fd)
    return status, held


def show(events=50):
    out = dict(schema='FRANKIE_QUEUE_SHOW_V1', queue=str(QUEUE), at=utc(),
               order_rule='arrival FIFO per line: enqueued_at then seq; days leave in exactly that order; nothing dropped, '
                          'skipped or reordered; one class at a time; school day = position in the class line = report N',
               lines={})
    for line in LINES:
        doc = load(line) if _path(line).is_file() else None
        status, held = worker_state(line)
        counts = {}
        for x in (doc or {}).get('entries') or []:
            counts[x['state']] = counts.get(x['state'], 0) + 1
        ev = QUEUE / ('%s-events.jsonl' % line)
        lines = ev.read_text(encoding='utf-8').splitlines() if ev.is_file() else []
        tail = lines if events == 'all' else lines[-int(events):] if int(events) > 0 else []
        out['lines'][line] = dict(file=str(_path(line)), exists=doc is not None, counts=counts,
                                  entries=line_view(doc, line) if doc else [], next_seq=(doc or {}).get('next_seq'),
                                  next_done_seq=(doc or {}).get('next_done_seq'),
                                  school_day_base=(doc or {}).get('school_day_base'),
                                  next_school_day=(doc or {}).get('next_school_day'),
                                  worker=status, worker_lock_held=held, events_total=len(lines),
                                  events_shown=len(tail), events=[json.loads(x) for x in tail])
    return out


# ------------------------------------------------------------------------------------------------------ workers

def _worker_status(line, **fields):
    path = QUEUE / ('%s-worker.json' % line)
    tmp = path.with_suffix('.pending')
    tmp.write_text(json.dumps(dict(fields, line=line, pid=os.getpid(), host=socket.gethostname(), at=time.time(),
                                   utc=utc()), indent=1, sort_keys=True, default=str) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def _take_worker_lock(line, wait=False):
    """The open lock file when this process is the line's one worker, else None (a worker runs already). wait=True
    blocks until the running worker releases it (the handover: the new worker starts the moment the old one ends)."""
    QUEUE.mkdir(parents=True, exist_ok=True)
    f = open(QUEUE / ('%s-worker.lock' % line), 'a+')
    try:
        fcntl.flock(f, fcntl.LOCK_EX if wait else fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        return None
    return f


@contextlib.contextmanager
def class_running(log=print):
    """Exactly one class at a time on the box: the classroom step holds this lock while its child runs (blocking)."""
    QUEUE.mkdir(parents=True, exist_ok=True)
    with open(QUEUE / 'class-running.lock', 'a+') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log('another class runs on this box (class-running.lock): this classroom waits for it (one class at a time)')
            fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def kick(line, code_root, commit, max_seconds, poll_seconds, by, log=print):
    """Start the line's worker detached (systemd-run, else a new session) unless one runs. The kicked worker is bounded by
    max_seconds like a dispatched one. Returns what happened (also an event)."""
    QUEUE.mkdir(parents=True, exist_ok=True)
    probe = _take_worker_lock(line)
    if probe is None:
        status, _ = worker_state(line)
        with locked():
            event(line, 'kick_worker_running', by=by, worker=(status or {}).get('pid'))
        return dict(started=False, reason='a %s worker runs (pid %s)' % (line, (status or {}).get('pid')))
    probe.close()                         # released: the new worker takes it (a race with another kick: one of them exits)
    (QUEUE / 'logs').mkdir(parents=True, exist_ok=True)
    log_path = QUEUE / 'logs' / ('%s-worker.log' % line)
    argv = [sys.executable, '-B', str(HERE / 'frankie_box_frankie_queue.py'), '--action', 'worker', '--line', line,
            '--code-root', str(code_root), '--commit', commit, '--max-seconds', str(int(max_seconds)),
            '--poll-seconds', str(int(poll_seconds))]
    env = dict(PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1', PYTHONPATH=str(code_root), HOME=os.environ.get('HOME') or '/root',
               MARKETS_SHA=commit, CODE_ROOT=str(code_root))
    how = None
    if shutil.which('systemd-run'):
        unit = 'frankie-queue-%s-%d' % (line, int(time.time()))
        cmd = ['systemd-run', '--unit', unit, '--collect', '-p', 'StandardOutput=append:%s' % log_path,
               '-p', 'StandardError=append:%s' % log_path] + [x for k, v in sorted(env.items()) for x in ('-E', '%s=%s' % (k, v))] + argv
        code = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).returncode
        how = dict(method='systemd-run', unit=unit, exit_code=code)
    if how is None or how['exit_code'] != 0:
        with open(log_path, 'ab') as out:
            proc = subprocess.Popen(argv, env=dict(os.environ, **env), stdout=out, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, start_new_session=True)
        how = dict(method='new session', pid=proc.pid, systemd_run=how)
    with locked():
        event(line, 'kick', by=by, commit=commit, code_root=str(code_root), max_seconds=max_seconds, how=how, log=str(log_path))
    log('%s worker started (%s); log %s' % (line, how, log_path))
    return dict(started=True, how=how, log=str(log_path))


def handover(line, code_root, commit, max_seconds, poll_seconds, log=print):
    """Move the line to new code without stopping any running day (2026-09-30): the running worker gets SIGTERM, which
    only stops it TAKING new work (its running days finish in their slots, then it ends and releases its lock); a new
    worker at this commit starts detached now and waits on the lock, so it takes over the moment the old one ends."""
    if line != 'root':
        raise SystemExit('handover is for the root line')
    status, held = worker_state(line)
    old = (status or {}).get('pid')
    signalled = None
    if held and old:
        try:
            cmd = Path('/proc/%d/cmdline' % int(old)).read_bytes().replace(b'\0', b' ').decode(errors='replace')
        except OSError:
            cmd = ''
        if 'frankie_box_frankie_queue.py' in cmd and '--action worker' in cmd and '--line root' in cmd:
            os.kill(int(old), signal.SIGTERM)
            signalled = int(old)
        else:
            raise SystemExit('the root worker lock is held but pid %s is not a root worker (%r): nothing signalled' % (old, cmd))
    (QUEUE / 'logs').mkdir(parents=True, exist_ok=True)
    log_path = QUEUE / 'logs' / ('%s-worker.log' % line)
    argv = [sys.executable, '-B', str(HERE / 'frankie_box_frankie_queue.py'), '--action', 'worker', '--line', line,
            '--code-root', str(code_root), '--commit', commit, '--max-seconds', str(int(max_seconds)),
            '--poll-seconds', str(int(poll_seconds)), '--wait-lock']
    env = dict(PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1', PYTHONPATH=str(code_root), HOME=os.environ.get('HOME') or '/root',
               MARKETS_SHA=commit, CODE_ROOT=str(code_root))
    unit = 'frankie-queue-%s-handover-%d' % (line, int(time.time()))
    cmd = ['systemd-run', '--unit', unit, '--collect', '-p', 'StandardOutput=append:%s' % log_path,
           '-p', 'StandardError=append:%s' % log_path] + [x for k, v in sorted(env.items()) for x in ('-E', '%s=%s' % (k, v))] + argv
    code = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).returncode
    with locked():
        event(line, 'handover', old_pid=old, signalled=signalled, unit=unit, exit_code=code, commit=commit)
    return dict(old_worker=old, signalled=signalled, new_unit=unit, systemd_run_exit=code, log=str(log_path),
                note='the old worker finishes the days in its slots and ends; the new one waits on the lock, then runs')


def _run_for(entry, code_root, commit, log):
    """(Run, plan day entry) of a queue entry: its run's saved plan (checked against the entry's plan_sha256) and the
    enqueuer's settings."""
    import frankie_box_experiment as X
    plan_path = X.RUNS / entry['run'] / 'plan.json'
    if not plan_path.is_file():
        raise RuntimeError('the run %s has no saved plan %s' % (entry['run'], plan_path))
    plan = json.loads(plan_path.read_bytes())
    if entry.get('plan_sha256') and X.plan_digest(plan) != entry['plan_sha256']:
        raise RuntimeError('the run %s holds another plan than the one the day was enqueued under (%s)' % (
            entry['run'], entry['plan_sha256']))
    e = next((d for d in plan['days'] if d['day'] == entry['day']), None)
    if e is None:
        raise RuntimeError('day %s is not in the run %s plan' % (entry['day'], entry['run']))
    a = argparse.Namespace(**dict(SETTINGS, **(entry.get('settings') or {})))
    return X.Run(a, plan, code_root, commit, log=log), e


class Bound(BaseException):
    """The class worker's time bound or a stop signal: save and end (a BaseException, so no step's own except Exception
    records it as the step's failure)."""


def _signal_bound(*_):
    raise Bound('stopped by a signal')


# ------------------------------------------------------------------------------------------------------ class line

def previous_for(doc, entry, plan):
    """The class the entry carries: (directory or None, None, where it came from, record)."""
    import frankie_box_experiment as X
    done = [x for x in doc['entries'] if x['state'] == 'done' and x.get('done_seq') and x.get('classroom')]
    if done:
        last = max(done, key=lambda x: x['done_seq'])
        rec = dict(seq=last['seq'], day=last['day'], run=last['run'], done_seq=last['done_seq'],
                   school_day=last.get('school_day'), classroom=last['classroom'], source='queue',
                   previous_trade_date_later=last['day'] > entry['day'])
        return last['classroom'], None, ('the class line: the last class to finish, seq %d day %s run %s (done #%d, school '
                                         'day %s)' % (last['seq'], last['day'], last['run'], last['done_seq'],
                                                      last.get('school_day'))), rec
    day_entry = next((d for d in plan.get('days') or [] if d.get('day') == entry['day']), {})
    for named, where in ((day_entry.get('previous_classroom'), 'plan (the day)'),
                         (plan.get('previous_classroom'), 'plan (PREVIOUS_CLASSROOM)')):
        if named:
            return named, None, 'bootstrap: %s; the class line has no done entry' % where, \
                dict(classroom=named, source='bootstrap_plan', named_in=where)
    found = []
    for completion in X.ROOTS.glob('*/work/classroom/completion.json'):
        try:
            r = json.loads((completion.parent / 'receipt.json').read_bytes())
        except (OSError, ValueError):
            continue
        if r.get('status') == 'complete' and str(completion.parent) != (entry.get('readiness') or {}).get('classroom'):
            found.append((completion.stat().st_mtime, str(completion.parent), str(r.get('day'))))
    if not found:
        return None, None, 'none: the class line has no done entry and the box no complete classroom (history starts here)', \
            dict(source='none')
    found.sort()
    t, d, day = found[-1]
    return d, None, ('bootstrap: the most recently finished complete classroom on the box (%s, day %s, %d complete '
                     'classrooms seen); the class line has no done entry' % (utc(t), day, len(found))), \
        dict(classroom=d, day=day, finished_utc=utc(t), source='bootstrap_box', candidates=len(found),
             previous_trade_date_later=day > entry['day'])


def school_day_of(doc, entry):
    """Assign the entry its school-day number when it is first taken (kept on every retry): the next number of the class
    line. The line starts after the numbers the reports index held when it first numbered a class (school_day_base,
    recorded with those days); a number another day took in the reports index meanwhile (a class run with the queue off)
    is passed over and recorded (school_days_outside_line), so no number is ever given to two days and none is left
    unused."""
    if entry.get('school_day'):
        return entry['school_day']
    import frankie_box_experiment as X
    import frankie_box_experiment_day_reports as R
    index = R.read_index(X.REPORTS) if X.REPORTS.is_dir() else dict(days=[], reports=[])
    held = {d['number']: d for d in index.get('days') or []}
    if X.REPORTS.is_dir():
        for p in X.REPORTS.iterdir():
            m = R.FILE_RE.match(p.name)
            if m:
                held.setdefault(int(m.group(2)), dict(file=p.name))
    if doc.get('school_day_base') is None:
        doc['school_day_base'] = max(held) if held else 0
        doc['school_day_base_days'] = [dict(number=n, **{k: v for k, v in d.items() if k in ('run', 'day', 'file')})
                                       for n, d in sorted(held.items())]
        doc['next_school_day'] = doc['school_day_base'] + 1
    while doc['next_school_day'] in held and not (held[doc['next_school_day']].get('run') == entry['run'] and
                                                  held[doc['next_school_day']].get('day') == entry['day']):
        n = doc['next_school_day']
        doc.setdefault('school_days_outside_line', []).append(dict(number=n, **{k: v for k, v in held[n].items()
                                                                                if k in ('run', 'day', 'file')}))
        doc['next_school_day'] = n + 1
    entry['school_day'] = doc['next_school_day']
    doc['next_school_day'] += 1
    return entry['school_day']


def passed(run, stage, day):
    """True when the step's receipt lets the next class-side step run."""
    import frankie_box_experiment as X
    r = run.receipt(stage, day)
    if not r:
        return False
    if stage == 'classroom':
        return r['status'] in ('done', 'reused')
    if stage == 'voice':
        return r['status'] in X.FINISHED or bool(r.get('not_wired') and r['status'] == 'waiting')
    if stage == 'reports' and run.reports_stale(dict(day=day)):
        return False
    return r['status'] in X.FINISHED


def frankie_lessons(run, e):
    """The scientific teacher on the day's own classroom novel findings (R09: only the novel findings of ledgers.json),
    over every discovery-day search of the run finished so far: the call the batch lessons make for a classroom-arm day,
    made here once the day's class is done (the orchestrator leaves queued days to the worker)."""
    import frankie_box_experiment as X
    day = e['day']
    if e['role'] != 'discovery':
        return run.record('frankie_lessons', day, 'skipped', reason='discovery days only (R15)')
    if e.get('frankie_ledgers'):
        return run.record('frankie_lessons', day, 'skipped', reason='the plan names the day\'s ledgers: the batch lessons '
                                                                    'call them')
    c = run.receipt('classroom', day)
    ledgers = Path(c['classroom']) / 'ledgers.json' if c and c.get('classroom') else None
    if ledgers is None or not ledgers.is_file():
        return run.record('frankie_lessons', day, 'skipped', reason='no ledgers.json in the day\'s classroom (%s)' % ledgers)
    written = run.lessons_written('frankie-%s' % day, [])
    if written:
        return run.record('frankie_lessons', day, 'reused', lessons=[str(w) for w in written])
    s = run.receipt('search', day)
    if not (s and s['status'] in X.FINISHED):
        return run.record('frankie_lessons', day, 'waiting', reason='the day\'s search is %s (Frankie\'s claims are tested '
                                                                    'on the searches)' % ((s or {}).get('status') or 'not run'))
    searched = [x['day'] for x in run.plan['days'] if x['role'] == 'discovery' and run.finished('search', x['day'])]
    searches = ','.join(str(X.SEARCH / d / ('cycle-' + X.CYCLE) / 'discovery') for d in searched)
    # a lessons call is a day-run step: run as stage 'lessons' so it books its 16 CPUs in the ledger like the batch calls
    code, log = run.child('lessons', day, 'frankie_box_scientific_teacher.sh',
                          dict(FRANKIE_LEDGERS=ledgers, FRANKIE_DAY=day, SEARCHES=searches))
    cpu = getattr(run, '_cpu', {}).pop(('lessons', day), None)
    written = run.lessons_written('frankie-%s' % day, [])
    if cpu and cpu['status'] == 'waiting' and not written:
        return run.record('frankie_lessons', day, 'waiting', exit_code=code, log=log, cpu_booking=cpu, reason=cpu['line'])
    if code != 0 or not written:
        return run.record('frankie_lessons', day, 'failed', exit_code=code, log=log, searched_days=searched, cpu_booking=cpu,
                          reason=(cpu or {}).get('line') if (cpu or {}).get('status') == 'refused' else
                          'no FRANKIE_LESSONS_V1 of the day after the call (its log names why)')
    return run.record('frankie_lessons', day, 'done', exit_code=code, log=log, searched_days=searched,
                      lessons=[str(w) for w in written], cpu_booking=cpu)


def class_day(entry, previous, school_day, code_root, commit, log):
    """Run the entry's class-side steps in order: ('done' | 'waiting' | 'failed', reason, facts)."""
    run, e = _run_for(entry, code_root, commit, log)
    day = e['day']
    run.school_day = school_day
    run.queue_previous = previous[:3]
    facts = dict(stages={})
    for stage in CLASS_STAGES:
        if passed(run, stage, day):
            r = run.receipt(stage, day)
        else:
            if stage == 'classroom':
                r = run.classroom(e)
                if r is not None:
                    run.reserve_after_classroom(e)
            elif stage == 'frankie_lessons':
                r = frankie_lessons(run, e)
            else:
                r = run.guarded(stage, e)
            if r is None:                                       # the disk floor: saved, the day waits
                why = (run.stopped or {}).get('reason')
                run.stopped = None
                return 'waiting', '%s: %s' % (stage, why), facts
        facts['stages'][stage] = dict(status=r['status'], reason=r.get('reason'),
                                      receipt=str(run.receipt_path(stage, day)))
        if passed(run, stage, day):
            continue
        if r['status'] == 'waiting':
            return 'waiting', '%s: %s' % (stage, r.get('reason')), facts
        if stage == 'classroom' and r['status'] == 'refused':
            rep = run.guarded('reports', e)                     # a refused day is reported too (with the reason)
            facts['stages']['reports'] = dict(status=rep['status'], reason=rep.get('reason'),
                                              receipt=str(run.receipt_path('reports', day)))
        return 'failed', '%s %s: %s' % (stage, r['status'], r.get('reason')), facts
    facts['classroom'] = run.receipt('classroom', day).get('classroom')
    return 'done', None, facts


def _plan_of(run_name):
    import frankie_box_experiment as X
    path = X.RUNS / run_name / 'plan.json'
    return json.loads(path.read_bytes()) if path.is_file() else {}


def _end_attempt(x, result, reason=None):
    att = (x.get('attempts') or [None])[-1]
    if att is not None and not att.get('ended'):
        att.update(ended=time.time(), ended_utc=utc(), result=result, reason=reason)


def _take_class(doc, x, commit):
    """Take the front entry (under the queue lock): a new attempt, its school-day number (assigned once, kept on a retry),
    the class it carries, and the report number reserved as that school day. Returns (previous, None) or (None, why the
    entry failed)."""
    import frankie_box_experiment as X
    import frankie_box_experiment_day_reports as R
    _end_attempt(x, 'worker gone', 'the attempt ended without a result (its worker is gone)')
    number = school_day_of(doc, x)
    previous = previous_for(doc, x, _plan_of(x['run']))
    x.setdefault('attempts', []).append(dict(pid=os.getpid(), host=socket.gethostname(), commit=commit, started=time.time(),
                                             started_utc=utc(), polls=0, school_day=number))
    x.update(state='running', reason='running (class worker pid %d, school day %d)' % (os.getpid(), number),
             previous=previous[3], previous_from=previous[2], taken_utc=x.get('taken_utc') or utc())
    try:
        got, assigned = R.reserve_number(X.REPORTS, x['run'], x['day'], number=number)
    except (Exception, SystemExit) as error:
        why = 'school day %d could not be reserved as the day\'s report number: %s' % (number, error)
        _end_attempt(x, 'failed', why)
        x.update(state='failed', reason=why)
        return None, why
    x['report_number'] = got
    event('class', 'take', seq=x['seq'], day=x['day'], run=x['run'], school_day=number, report_number=got,
          report_number_assigned_now=assigned, previous=previous[3])
    return previous, None


def class_worker(code_root, commit, max_seconds, poll_seconds, log=print):
    """The one class worker: the front of the class line, one day at a time, polled while it waits."""
    lock = _take_worker_lock('class')
    if lock is None:
        status, _ = worker_state('class')
        log('a class worker runs already (pid %s): this one ends; the running worker takes every entry' % (status or {}).get('pid'))
        return 0
    signal.signal(signal.SIGTERM, _signal_bound)
    sys.path.insert(0, str(HERE))
    from frankie_box_progress import Probe
    probe = Probe(QUEUE / 'class-worker', phase='frankie-queue-class')
    deadline = time.monotonic() + max_seconds
    retried, current, previous, code = set(), None, None, 0
    _worker_status('class', state='running', commit=commit, code_root=str(code_root), max_seconds=max_seconds,
                   poll_seconds=poll_seconds, started_utc=utc())

    def release():
        nonlocal lock
        if lock is not None:
            fcntl.flock(lock, fcntl.LOCK_UN)          # released under the queue lock: an entry enqueued now gets a new kick
            lock.close()
            lock = None

    try:
        while True:
            with locked():
                doc = load('class')
                x = front(doc)
                n_done = sum(1 for y in doc['entries'] if y['state'] == 'done')
                if x is None or (x['state'] == 'failed' and x['seq'] in retried):
                    state = 'idle' if x is None else 'stopped_at_failed'
                    about = None if x is None else dict(seq=x['seq'], day=x['day'], run=x['run'], reason=x.get('reason'))
                    _worker_status('class', state=state, commit=commit, front=about)
                    event('class', 'worker_end', state=state, front=about)
                    probe.update('class:' + state, n_done, len(doc['entries']) or None,
                                 state='complete' if x is None else 'failed')
                    release()
                    code = 0 if x is None else 3
                    break
                mine = (x['state'] == 'running' and x['seq'] == current and
                        (x.get('attempts') or [{}])[-1].get('pid') == os.getpid())
                if not mine:
                    if time.monotonic() >= deadline:
                        raise Bound('the time bound (%d s) before taking seq %d' % (max_seconds, x['seq']))
                    if x['state'] == 'failed':
                        retried.add(x['seq'])            # a failed front is retried once per worker start, never skipped
                    previous, why = _take_class(doc, x, commit)
                    save('class', doc)
                    if previous is None:
                        event('class', 'failed', seq=x['seq'], day=x['day'], run=x['run'], reason=why)
                        retried.add(x['seq'])
                        continue
                    current = x['seq']
                entry = dict(x)
            _worker_status('class', state='running', commit=commit, front=dict(seq=entry['seq'], day=entry['day'],
                                                                              run=entry['run'],
                                                                              school_day=entry.get('school_day')))
            probe.update('class:%s:%s' % (entry['day'], entry['run']), n_done, len(doc['entries']) or None, in_flight=1)
            try:
                result, reason, facts = class_day(entry, previous, entry['school_day'], code_root, commit, log)
            except (Exception, SystemExit) as error:     # recorded on the entry; the line stops there (retried once)
                result, reason, facts = 'failed', '%s: %s' % (type(error).__name__, error), {}
            with locked():
                doc = load('class')
                y = find(doc, current)
                y['stages'] = facts.get('stages') or y.get('stages') or {}
                y['receipts'] = [dict(stage=s, **v) for s, v in (facts.get('stages') or {}).items()]
                att = y['attempts'][-1]
                if result == 'done':
                    _end_attempt(y, 'done')
                    y.update(state='done', reason=None, done_seq=doc['next_done_seq'], done_at=time.time(), done_utc=utc(),
                             classroom=facts.get('classroom'))
                    doc['next_done_seq'] += 1
                    save('class', doc)
                    event('class', 'done', seq=y['seq'], day=y['day'], run=y['run'], done_seq=y['done_seq'],
                          school_day=y.get('school_day'), classroom=y['classroom'], stages=y['stages'])
                    log('class seq %d %s (%s): done, school day %s' % (y['seq'], y['day'], y['run'], y.get('school_day')))
                    current = None
                    continue
                if result == 'failed':
                    _end_attempt(y, 'failed', reason)
                    y.update(state='failed', reason=reason)
                    save('class', doc)
                    event('class', 'failed', seq=y['seq'], day=y['day'], run=y['run'], reason=reason)
                    log('class seq %d %s (%s): failed: %s (the line stops here; never skipped)' % (
                        y['seq'], y['day'], y['run'], reason))
                    current = None
                    continue                                   # the loop ends at this failed front after one retry
                att['polls'] = att.get('polls', 0) + 1
                att['last_wait'] = reason
                y['reason'] = 'waiting (poll %d): %s' % (att['polls'], reason)
                save('class', doc)
                if att['polls'] == 1 or att['polls'] % 60 == 0:
                    event('class', 'waiting', seq=y['seq'], day=y['day'], run=y['run'], polls=att['polls'], reason=reason)
            if time.monotonic() + poll_seconds > deadline:
                raise Bound('the time bound (%d s) while seq %d waited: %s' % (max_seconds, current, reason))
            time.sleep(poll_seconds)
    except Bound as stop:
        code = 5
        with locked():
            doc = load('class')
            if current is not None:
                y = find(doc, current)
                if y['state'] == 'running':
                    _end_attempt(y, 'saved', str(stop))
                    y.update(state='queued', reason='saved at the worker bound (%s); the next worker start resumes it, '
                                                    'finished steps skipped, same school day %s' % (stop, y.get('school_day')))
                    save('class', doc)
            event('class', 'worker_saved', reason=str(stop), front=current)
            _worker_status('class', state='saved', reason=str(stop), commit=commit)
            release()
    return code


# ------------------------------------------------------------------------------------------------------ ROOT line

def box_slots(settings):
    """The free box day-run slots right now, from the box's CPU booking ledger (frankie_box_cores.py, Greg 2026-09-29:
    "Correct 16 and no double booking"): a slot is EXACTLY DAY_RUN_CPUS (16) CPUs, so the free slots are the ledger's free
    CPUs (online, less live bookings, less CPUs in use by Frankie processes outside the ledger: its own usage() rule, read
    only here) divided by 16. The ROOT step books its 16 itself when it starts (Run.child runs it through
    frankie_box_cores.py run); one that cannot book them (another booking landed in between) records waiting and goes
    back to its own place in the line. Without the ledger module on the box: the enqueuer's PARALLEL_DAYS. Returns (free
    slots now or None, total or None, source)."""
    try:
        import frankie_box_cores as C
    except ImportError:
        return None, max(1, int(settings.get('parallel_days') or 1)), 'PARALLEL_DAYS (frankie_box_cores.py not on the box)'
    me = os.getpid()
    held, _, _, bookings = C.usage(1.0, exclude=C.ancestors(C.processes(), me) | {me})
    booked = {c for b in bookings for c in b['cpus']}
    free = [c for c in C.online_cpus() if c not in booked and c not in held]
    return len(free) // C.DAY_RUN_CPUS, len(C.online_cpus()) // C.DAY_RUN_CPUS, \
        'frankie_box_cores: %d free CPUs = %d slot(s) of %d' % (len(free), len(free) // C.DAY_RUN_CPUS, C.DAY_RUN_CPUS)


def root_gate(run, day):
    """(True, why) when a Pod may claim the day now under the ROOT line; (False, why) otherwise. A run with no entry in the
    line claims as before (the line is not used by it)."""
    import frankie_box_root_claims as claims
    try:
        doc = load('root')
    except (OSError, ValueError, SystemExit) as error:
        return False, 'root_line_unreadable: the ROOT line could not be read (%s)' % error
    if not any(x['run'] == run for x in doc['entries']):
        return True, 'the run %s has no entry in the ROOT line (claims as before)' % run
    mine = next((x for x in doc['entries'] if x['run'] == run and x['day'] == day), None)
    if mine is None:
        return False, 'not_in_root_line: %s enters the ROOT line when it is ROOT-ready (orchestrator)' % day
    if mine['state'] == 'done':
        return False, 'root_line_done: the day\'s ROOT line entry is done (seq %d)' % mine['seq']
    for x in ordered(doc):
        if x['seq'] >= mine['seq']:
            break
        if x['state'] == 'failed':
            return False, 'behind_in_root_line: seq %d day %s run %s failed; the line stops there (never skipped)' % (
                x['seq'], x['day'], x['run'])
        started = x['state'] in ('running', 'done') or (claims.active() and claims.holder(x['run'], x['day']))
        if not started:
            return False, 'behind_in_root_line: seq %d day %s run %s goes first (arrival FIFO)' % (x['seq'], x['day'], x['run'])
    return True, 'the front of the ROOT line (seq %d)' % mine['seq']


def root_claimed(run, day, where, attempt, by):
    """A claim of a line day taken outside the box worker (a Pod): the entry is running there."""
    with locked():
        doc = load('root')
        x = next((y for y in doc['entries'] if y['run'] == run and y['day'] == day), None)
        if x is None or x['state'] == 'done':
            return
        x.setdefault('attempts', []).append(dict(where=where, attempt=attempt, started=time.time(), started_utc=utc(), by=by))
        x.update(state='running', where=where, reason='claimed by %s (attempt %s)' % (where, attempt))
        save('root', doc)
        event('root', 'claimed', seq=x['seq'], day=day, run=run, where=where, attempt=attempt, by=by)


def _after_root(run, e, code_root, commit, log):
    """A finished ROOT of a line day: an arm day whose teacher rows are there enters the class line at once (the
    classroom step's own readiness checks), and the class worker is kicked. Returns what happened, for the entry."""
    if not (e['classroom_arm'] and getattr(run.a, 'frankie_queue', 'on') == 'on') or run.finished('classroom', e['day']):
        return None
    c = run.enqueue_classroom(e)
    out = dict(status=(c or {}).get('status'), seq=(c or {}).get('queue_seq'), reason=(c or {}).get('reason'))
    if (c or {}).get('status') == 'queued':
        kick('class', code_root, commit, run.a.queue_worker_seconds, run.a.queue_poll_seconds,
             by='ROOT line after %s %s' % (run.plan['run'], e['day']), log=log)
    return out


TEACHER_BOOK_WAIT = 1800        # seconds the slot's teacher retries a CPU booking the slot itself just released


def _finish_day(run, e, code_root, commit, log):
    """The rest of the day in the SAME slot (Greg, 2026-09-30: "the days are supposed to go through all of the processes
    until everything is done for that day"; "no more days quit before the end"): the day's own teacher rows (a batch of
    this one day, key day-<YYYYMMDD>; the rows are per day either way), then the class line for an arm day. The slot is
    held by the worker's thread from the ROOT to here, so no other day takes it in between. A teacher that finds its 16
    CPUs taken (another runner booked them in the gap) retries for TEACHER_BOOK_WAIT seconds. Returns (ok, facts)."""
    import frankie_box_experiment as X
    facts = {}
    if X.rows_of(e)[0] is None:
        deadline = time.monotonic() + TEACHER_BOOK_WAIT
        while True:
            t = run.teacher('day-%s' % e['day'], [e]) or {}
            if t.get('status') != 'waiting' or X.rows_of(e)[0] is not None or time.monotonic() > deadline:
                break
            log('teacher %s %s: waiting (%s); retrying in the held slot' % (run.plan['run'], e['day'], t.get('reason')))
            time.sleep(30)
        facts['teacher'] = dict(status=t.get('status'), reason=t.get('reason'), log=t.get('log'))
        if X.rows_of(e)[0] is None:
            return False, facts
    else:
        facts['teacher'] = dict(status='rows present', rows=str(X.rows_of(e)[0]))
    facts['class_line'] = _after_root(run, e, code_root, commit, log)
    return True, facts


def _finish_job(entry, code_root, commit, log, holder):
    """A day whose ROOT is done but whose day is not (its ROOT ran on a Pod, or before the whole-day rule): the rest
    of the day in a box slot, ahead of any new ROOT (Greg, 2026-09-30: "when 2 spots open put them back so they can
    finish")."""
    try:
        run, e = _run_for(entry, code_root, commit, log)
        ok, facts = _finish_day(run, e, code_root, commit, log)
        holder['result'] = ('finished' if ok else 'finish_failed',
                            None if ok else 'teacher: %s' % (facts.get('teacher') or {}).get('reason'), facts)
    except (Exception, SystemExit) as error:
        holder['result'] = ('finish_failed', '%s: %s' % (type(error).__name__, error), {})


def _needs_finish(x, plans):
    """A done ROOT-line entry whose day still lacks its teacher rows (the rest of the day not run)."""
    import frankie_box_experiment as X
    if x['state'] != 'done' or (x.get('finish') or {}).get('state') == 'finished':
        return False
    if x['run'] not in plans:
        plans[x['run']] = _plan_of(x['run'])
    e = next((d for d in plans[x['run']].get('days') or [] if d['day'] == x['day']), None)
    return e is not None and X.rows_of(e)[0] is None


def _root_job(entry, code_root, commit, log, holder):
    """One day in a box slot (a thread): the orchestrator's own root step, then the rest of the day in the same slot."""
    try:
        run, e = _run_for(entry, code_root, commit, log)
        r = run.root(e)
        if r is None:
            holder['result'] = ('queued', 'the disk floor: %s' % (run.stopped or {}).get('reason'), {})
        elif r['status'] in ('done', 'reused'):
            ok, facts = _finish_day(run, e, code_root, commit, log)
            holder['result'] = ('done', None, dict(facts, calculations=r.get('calculations'), root_status=r['status'],
                                                   finish='finished' if ok else 'finish_failed'))
        elif r['status'] == 'waiting' and r.get('claim'):
            holder['result'] = ('claimed_elsewhere', r.get('reason'), dict(claim=r.get('claim')))
        elif r['status'] == 'waiting':
            holder['result'] = ('queued', r.get('reason'), {})
        else:
            holder['result'] = ('failed', '%s: %s' % (r['status'], r.get('reason')), dict(log=r.get('log')))
    except (Exception, SystemExit) as error:          # a refusal (SystemExit) is the day's failure, never the worker's
        holder['result'] = ('failed', '%s: %s' % (type(error).__name__, error), {})


def _sync_root(doc, x, plans):
    """An entry this worker is not running: done when its ROOT is finished (a Pod import, another runner, an earlier
    attempt), running when an open claim holds it elsewhere or a ROOT of the day still runs on the box, queued again at
    its own place when its runner is gone. Returns the change or None."""
    import frankie_box_experiment as X
    import frankie_box_root_claims as claims
    if x['run'] not in plans:
        plans[x['run']] = _plan_of(x['run'])
    e = next((d for d in plans[x['run']].get('days') or [] if d['day'] == x['day']), None)
    if e is None:
        if x['state'] != 'failed':
            x.update(state='failed', reason='day %s is not in the saved plan of run %s' % (x['day'], x['run']))
            return 'failed'
        return None
    try:
        calc, _ = X.root_of(e, x['run'])
    except SystemExit as refusal:
        if x['state'] == 'failed' and x.get('reason') == str(refusal):
            return None
        x.update(state='failed', reason=str(refusal))
        return 'failed'
    if calc is None and x['state'] == 'failed':
        return None                                  # a failed entry stays failed (retried once per worker start)
    if calc is not None:
        _end_attempt(x, 'done', 'a finished ROOT found: %s' % calc)
        x.update(state='done', reason=None, calculations=str(calc), done_seq=doc['next_done_seq'], done_at=time.time(),
                 done_utc=utc(), done_by='a finished ROOT found (%s)' % (x.get('where') or 'another runner'),
                 needs_receipt=True)
        doc['next_done_seq'] += 1
        return 'done'
    held = claims.holder(x['run'], x['day']) if claims.active() else None
    if held and not held.get('done') and not str(held.get('where') or '').startswith('box:'):
        if x['state'] != 'running' or x.get('where') != held.get('where'):
            x.update(state='running', where=held.get('where'), reason='claimed by %s (attempt %s)' % (
                held.get('where'), held.get('attempt')))
            return 'running'
        return None
    if x['state'] == 'running':
        if claims.root_running(x['day']):
            x['reason'] = 'a ROOT of the day still runs on the box (from a stopped worker or orchestrator): waited for'
            return None
        _end_attempt(x, 'runner gone', 'no open claim elsewhere, no finished ROOT, no ROOT of the day running here')
        x.update(state='queued', where=None, reason='its runner %s is gone: in line again at its own place' % x.get('where'))
        return 'queued'
    return None


def root_worker(code_root, commit, max_seconds, poll_seconds, log=print, wait_lock=False):
    """The one ROOT worker: box slots filled from the front of the ROOT line in arrival order; Pod claims followed. It
    never starts a ROOT after its bound or a stop signal, and waits for the ROOTs it started (their receipts are theirs).
    Each box-slot day runs its whole day in the slot (ROOT, its teacher, the class line); days whose ROOT is done but
    whose day is not take free slots first."""
    lock = _take_worker_lock('root', wait=wait_lock)
    if lock is None:
        status, _ = worker_state('root')
        log('a ROOT worker runs already (pid %s): this one ends; the running worker takes every entry' % (status or {}).get('pid'))
        return 0
    stop = {}
    signal.signal(signal.SIGTERM, lambda *_: stop.setdefault('reason', 'stopped by a signal'))
    sys.path.insert(0, str(HERE))
    from frankie_box_progress import Probe
    probe = Probe(QUEUE / 'root-worker', phase='frankie-queue-root')
    deadline = time.monotonic() + max_seconds
    running, retried, plans, code = {}, set(), {}, 0
    _worker_status('root', state='running', commit=commit, code_root=str(code_root), max_seconds=max_seconds,
                   poll_seconds=poll_seconds, started_utc=utc())
    while True:
        if time.monotonic() >= deadline:
            stop.setdefault('reason', 'the time bound (%d s)' % max_seconds)
        finished = [seq for seq, job in running.items() if not job['thread'].is_alive()]
        after = []
        with locked():
            doc = load('root')
            for seq in finished:
                job = running.pop(seq)
                y = find(doc, seq)
                result, reason, facts = job['holder'].get('result') or ('failed', 'the slot ended without a result', {})
                if job.get('kind') == 'finish':
                    y['finish'] = dict(y.get('finish') or {}, state='finished' if result == 'finished' else 'failed',
                                       reason=reason, ended_utc=utc(), facts=facts)
                    event('root', 'finish_end', seq=seq, day=y['day'], run=y['run'], result=result, reason=reason, facts=facts)
                    log('FINISH seq %d %s (%s): %s%s' % (seq, y['day'], y['run'], result, (': %s' % reason) if reason else ''))
                    continue
                _end_attempt(y, result, reason)
                y['attempts'][-1].update(facts)
                if result == 'done':
                    y.update(state='done', reason=None, where='box-slot', calculations=facts.get('calculations'),
                             class_line=facts.get('class_line'), done_seq=doc['next_done_seq'], done_at=time.time(),
                             done_utc=utc(), finish=dict(state='finished' if facts.get('finish') == 'finished' else 'failed',
                                                         facts={k: facts.get(k) for k in ('teacher', 'class_line')},
                                                         ended_utc=utc()))
                    doc['next_done_seq'] += 1
                elif result == 'claimed_elsewhere':
                    y.update(state='running', where=(facts.get('claim') or {}).get('where'), reason=reason)
                elif result == 'queued':
                    y.update(state='queued', where=None, reason='back in line at its own place: %s' % reason)
                else:
                    y.update(state='failed', where=None, reason=reason)
                event('root', 'slot_end', seq=seq, day=y['day'], run=y['run'], result=result, reason=reason, facts=facts)
                log('ROOT seq %d %s (%s): %s%s' % (seq, y['day'], y['run'], result, (': %s' % reason) if reason else ''))
            for x in ordered(doc):
                if x['state'] != 'done' and x['seq'] not in running:
                    change = _sync_root(doc, x, plans)
                    if change:
                        event('root', 'sync_' + change, seq=x['seq'], day=x['day'], run=x['run'], reason=x.get('reason'),
                              where=x.get('where'))
                if x['state'] == 'done' and x.pop('needs_receipt', None):
                    after.append(dict(x))
            free, blocked, source = None, None, None

            def slots_now(x):
                f, total, src = box_slots(x.get('settings') or {})
                if total is None:
                    total = f if f is not None else 0
                # a slot whose day is between two bookings (ROOT ended, teacher not booked yet) is still that day's
                return (min(f, total - len(running)) if f is not None else total - len(running)), src

            # first the days whose ROOT is done but whose day is not: back into a slot ahead of any new ROOT
            for x in ordered(doc):
                if stop or x['seq'] in running or not _needs_finish(x, plans):
                    continue
                if (x.get('finish') or {}).get('state') == 'failed':
                    if x['seq'] in retried:
                        continue                            # a failed finish is retried once per worker start
                    retried.add(x['seq'])
                if free is None:
                    free, source = slots_now(x)
                if free <= 0:
                    break
                holder = {}
                x['finish'] = dict(state='running', started_utc=utc(), pid=os.getpid(), commit=commit)
                t = threading.Thread(target=_finish_job, args=(dict(x), code_root, commit, log, holder), daemon=True)
                running[x['seq']] = dict(thread=t, holder=holder, kind='finish')
                t.start()
                free -= 1
                event('root', 'finish_take', seq=x['seq'], day=x['day'], run=x['run'], where='box-slot', slots=source)
            for x in ordered(doc):
                if x['state'] in ('done', 'running'):
                    continue
                if x['state'] == 'failed':
                    if x['seq'] in retried:
                        blocked = x
                        break                               # the line stops at a failed entry (never skipped)
                    retried.add(x['seq'])                   # retried once per worker start
                if stop:
                    break
                if free is None:
                    free, source = slots_now(x)
                if free <= 0:
                    break                                   # no free slot: everything behind the front waits
                holder = {}
                x.setdefault('attempts', []).append(dict(where='box-slot', pid=os.getpid(), commit=commit,
                                                         started=time.time(), started_utc=utc(), slots=source))
                x.update(state='running', where='box-slot', reason='running in a box slot (%s)' % source)
                t = threading.Thread(target=_root_job, args=(dict(x), code_root, commit, log, holder), daemon=True)
                running[x['seq']] = dict(thread=t, holder=holder)
                t.start()
                free -= 1
                event('root', 'take', seq=x['seq'], day=x['day'], run=x['run'], where='box-slot', slots=source)
            save('root', doc)
            pending = [x for x in doc['entries'] if x['state'] != 'done' or
                       (x.get('finish') or {}).get('state') not in ('finished', 'failed') and _needs_finish(x, plans)]
            n_done = len(doc['entries']) - len(pending)
            end = None
            if not running and not pending and not after:
                end = ('idle', 0)
            elif not running and not after and blocked is not None and all(x['state'] != 'running' for x in pending):
                end = ('stopped_at_failed', 3)
            elif not running and stop and not after:
                end = ('saved', 5)
            if end:
                about = None if blocked is None else dict(seq=blocked['seq'], day=blocked['day'], run=blocked['run'],
                                                          reason=blocked.get('reason'))
                _worker_status('root', state=end[0], commit=commit, reason=stop.get('reason'), front=about,
                               pending=len(pending))
                event('root', 'worker_end', state=end[0], reason=stop.get('reason'), front=about, pending=len(pending))
                probe.update('root:' + end[0], n_done, len(doc['entries']) or None,
                             state='complete' if end[1] == 0 else 'failed')
                fcntl.flock(lock, fcntl.LOCK_UN)            # released under the queue lock: an enqueue now gets a new kick
                lock.close()
                code = end[1]
                break
        for x in after:                                     # a ROOT finished elsewhere: its step receipt, then the class line
            try:
                run, e = _run_for(x, code_root, commit, log)
                r = run.root(e)
                cls = _after_root(run, e, code_root, commit, log) if r and r['status'] in ('done', 'reused') else None
                with locked():
                    event('root', 'receipt_after_found', seq=x['seq'], day=x['day'], run=x['run'],
                          root_status=(r or {}).get('status'), class_line=cls)
            except Exception as error:                      # listed; the orchestrator's next start records it too
                with locked():
                    event('root', 'receipt_after_found_failed', seq=x['seq'], day=x['day'], run=x['run'],
                          reason='%s: %s' % (type(error).__name__, error))
        _worker_status('root', state='running', commit=commit, running=sorted(running), stop=stop.get('reason'),
                       pending=len(pending))
        probe.update('root:running %d' % len(running), n_done, len(doc['entries']) or None, in_flight=len(running))
        time.sleep(poll_seconds)
    return code


# ------------------------------------------------------------------------------------------------------ main

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--action', required=True, choices=('show', 'enqueue', 'worker', 'kick', 'handover'))
    p.add_argument('--wait-lock', action='store_true', help='worker: wait for the running worker to end (handover)')
    p.add_argument('--line', choices=LINES)
    p.add_argument('--code-root')
    p.add_argument('--commit')
    p.add_argument('--run')
    p.add_argument('--day')
    p.add_argument('--events', default='50', help='show: how many of the last events per line (a number or all)')
    p.add_argument('--max-seconds', type=int, default=1500)
    p.add_argument('--poll-seconds', type=int, default=60)
    p.add_argument('--kick', choices=('on', 'off'), default='on', help='enqueue: kick the line\'s worker after')
    a = p.parse_args()
    if a.action == 'show':
        if a.events != 'all' and not a.events.isdigit():
            raise SystemExit('--events: a number or all')
        print(json.dumps(show(a.events), indent=1, sort_keys=True, default=str))
        return 0
    if not (a.line and a.code_root and a.commit):
        raise SystemExit('--line, --code-root and --commit required')
    if a.max_seconds < 60 or a.poll_seconds < 5 or a.poll_seconds > 600:
        raise SystemExit('--max-seconds >= 60 and --poll-seconds 5..600 required')
    sys.path.insert(0, str(HERE))
    if a.action == 'worker':
        if a.line == 'class':
            code = class_worker(a.code_root, a.commit, a.max_seconds, a.poll_seconds, log=lambda t: print(t, flush=True))
        else:
            code = root_worker(a.code_root, a.commit, a.max_seconds, a.poll_seconds, log=lambda t: print(t, flush=True),
                               wait_lock=a.wait_lock)
        print(json.dumps(show(20)['lines'][a.line], indent=1, sort_keys=True, default=str))
        return code
    if a.action == 'kick':
        print(json.dumps(kick(a.line, a.code_root, a.commit, a.max_seconds, a.poll_seconds, by='dispatch'), sort_keys=True))
        return 0
    if a.action == 'handover':
        print(json.dumps(handover(a.line, a.code_root, a.commit, a.max_seconds, a.poll_seconds), sort_keys=True, default=str))
        return 0
    # enqueue: the orchestrator's own readiness checks on the run's saved plan, then the entry (and the kick)
    import re
    if not (a.run and re.fullmatch('[A-Za-z0-9_-]{1,64}', a.run) and a.day and re.fullmatch('[0-9]{8}', a.day)):
        raise SystemExit('--run [A-Za-z0-9_-] and --day YYYYMMDD required')
    entry = dict(run=a.run, day=a.day, settings=dict(SETTINGS, queue_poll_seconds=a.poll_seconds))
    run, e = _run_for(entry, a.code_root, a.commit, log=lambda t: print(t, flush=True))
    r = run.enqueue_classroom(e) if a.line == 'class' else run.root_enqueue(e)
    print(json.dumps(r, indent=1, sort_keys=True, default=str))
    if (r or {}).get('status') == 'queued' and a.kick == 'on':
        print(json.dumps(kick(a.line, a.code_root, a.commit, SETTINGS['queue_worker_seconds'], a.poll_seconds,
                              by='dispatch enqueue'), sort_keys=True))
    return 0 if (r or {}).get('status') in ('queued', 'done', 'reused') else 3


if __name__ == '__main__':
    sys.exit(main())
