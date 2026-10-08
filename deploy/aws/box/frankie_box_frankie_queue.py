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
and flagged previous_trade_date_later. Greg 2026-10-06: this experiment's school reader also uses completed workflow
order, not trading-date order; learned discovery knowledge from later market dates is eligible at the next boundary.

WHAT THE CLASS WORKER RUNS per day (everything that carries his previous day), in order, through the orchestrator's own
step methods (frankie_box_experiment.Run; nothing re-implemented): classroom FIRST, then data export and causal search,
batch scientific-teacher lessons, Frankie's own novel findings tested, exchange, voice (not wired: passes as listed),
school and reports. Jev's material relay stays the orchestrator's step (a hand-off to
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
foreground, bounded by MAX_SECONDS), kick (LINE: starts the detached worker unless one runs), save / status / resume
(RUN DAY: the owner contract below). No model call, no Pod call, no Granite, no Databento.

THE OWNER CONTRACT (Step 8, 2026-10-07). A ROOT-line day taken into a box slot is bound to its OWNER before its thread
starts: run, day, host, the exact ROOT attempt name (a completed ROOT's, else the next after the day's interrupted
attempts), commit and staged checkout, the exact 16-CPU set and booking, and a DAY-BOUND SAVE MARKER
(save/<run>-<day>.save-request.json). The Run reads its own marker and hands it to its children only; two main lanes in
one worker process never share one. ACTION=save writes the marker; the owner stops at its next boundary (exit 75).
A class-arm day in its class phase waits for the CLASS CHILD'S ACKNOWLEDGMENT (the class worker, on the same marker,
ends the class saved and writes an ack bound to that marker, its booking and the owner's attempt) before it ends saved;
a child gone without one makes the day UNKNOWN, never saved. saved/unknown days keep their attempt, booking and CPUs
(the ledger retains the booking: nobody else books those CPUs) and are never admitted, retried or requeued on their
own: ACTION=resume archives the marker and ack, puts the entries back in line with the same owner binding, and the next
admission books exactly the retained CPUs and resumes the same attempt. ACTION=status reports the owner, the marker,
the acknowledgment, the booking and the worker distinctly. Exit 75 is never a failure or a requeue; no replacement
attempt is minted for an owned day; a save never bypasses an unfinished Jev dependency (the day stops at its boundary
with Jev still waiting).
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
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
KICK_LOCK_WAIT_SECONDS = 60          # kick waits up to this for the started worker to hold its lock (B3a)
KICK_GRACE_SECONDS = 900             # a kick this recent keeps the box in use (KeepRunning) even before its worker's lock
STATES = ('queued', 'running', 'done', 'failed', 'saved', 'unknown')
# saved: the day's owner stopped at a boundary on its day-bound save marker and retains its attempt, exact CPU set and
#        booking; it leaves this state only through ACTION=resume (never ordinary admission or a failure retry).
# unknown: the owner's process is gone without a saved result or acknowledgment (a kill, a crash); its attempt, CPUs and
#        booking are retained; ACTION=resume reconciles and resumes it, nothing requeues it on its own.
SAVE_DIR = QUEUE / 'save'                 # <run>-<day>.save-request.json: the day-bound save marker; its acknowledgments beside it
OWNER_STATES = ('saved', 'unknown')


# THE AUTHORIZED SCOPE (Step 8, 2026-10-07). Every worker is started FOR an exact run and set of days ("RUN:D1,D2,...",
# the orchestrator's saved plan days or a dispatch's one day). It reconciles, admits, finishes and receipts only entries
# inside that scope; an entry outside it is left exactly as it is (never admitted, requeued, failed or deleted). FIFO
# holds within the eligible scope: an out-of-scope predecessor that has not started makes the eligible day behind it
# wait (the line is never reordered), and it is never started by this worker (a predecessor cannot widen the
# authorization). A kick without a scope is refused; a restart carries its own scope and never expands it.

def parse_scope(text):
    """'RUN:D1,D2' (or a parsed scope) -> {'run': RUN, 'days': {D1, D2}, 'text': ...}; refuses anything else."""
    import re
    if isinstance(text, dict):
        text = text.get('text')
    run, sep, days = (text or '').partition(':')
    if not sep or not re.fullmatch('[A-Za-z0-9_-]{1,64}', run):
        raise SystemExit('--scope RUN:YYYYMMDD,... required (the authorized run and days)')
    out = [d for d in days.split(',') if d]
    if not out or not all(re.fullmatch('[0-9]{8}', d) for d in out) or len(set(out)) != len(out):
        raise SystemExit('--scope days must be distinct YYYYMMDD values')
    return dict(run=run, days=set(out), text='%s:%s' % (run, ','.join(out)))


def in_scope(x, scope):
    return x['run'] == scope['run'] and x['day'] in scope['days']
CLASS_STAGES = ('classroom', 'data', 'search', 'batch_lessons', 'frankie_lessons', 'exchange', 'voice', 'school', 'reports')
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
                 class_line=x.get('class_line'), readiness=x.get('readiness'), line_state=x['state'],
                 source_owner=x.get('source_owner'), owner=x.get('owner'), save_request=x.get('save_request'),
                 save_ack=x.get('save_ack'), finish=x.get('finish'))
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


CPU_WATCH_SCRIPT = 'deploy/aws/box/frankie_box_cpu_watch.sh'


def _start_cpu_watch(code_root, log=print, script=None):
    """Session 8 (Greg, decision 4): every kick starts the CPU watchdog loop (frankie_box_cpu_watch.sh ACTION=loop on the
    kicked checkout: idempotent under its own systemd unit / flock; re-pin and resize ON unless the kicker's env says off),
    so it runs without anyone remembering. Its outcome goes on the kick record; it is never a reason to refuse the kick."""
    script = Path(script) if script else Path(code_root) / CPU_WATCH_SCRIPT
    if not script.is_file():
        return dict(started=False, reason='no %s in %s (that checkout predates the watchdog)' % (CPU_WATCH_SCRIPT, code_root))
    try:
        out = subprocess.run(['sh', str(script)], env=dict(os.environ, ACTION='loop', CODE_ROOT=str(code_root)),
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        return dict(started=False, reason='%s: %s' % (type(error).__name__, error))
    text = out.stdout.decode('utf-8', 'replace').strip()
    log('cpu watch loop: exit %d; %s' % (out.returncode, text[-300:]))
    return dict(started=out.returncode == 0, exit_code=out.returncode, output=text[-600:], script=str(script))


def kick(line, code_root, commit, max_seconds, poll_seconds, by, log=print, scope=None):
    """Start the line's worker detached (systemd-run, else a new session) unless one runs, FOR the authorized scope
    (RUN:days; refused without one). The kicked worker is bounded by max_seconds like a dispatched one. A running worker
    keeps its own scope: a day outside it waits for the next kick after that worker ends. Returns what happened."""
    if scope is None:
        # a kick without an authorization starts nothing (never an unscoped worker): the day waits for a scoped kick
        with locked():
            event(line, 'kick_refused_no_scope', by=by)
        log('%s worker not kicked by %s: no scope given (RUN:days); the line waits for a scoped kick' % (line, by))
        return dict(started=False, reason='no scope given: a worker is started only for an authorized RUN:days')
    scope = parse_scope(scope)
    QUEUE.mkdir(parents=True, exist_ok=True)
    probe = _take_worker_lock(line)
    if probe is None:
        # the lock's fast path never bypasses the scope: the running worker's PERSISTED scope (its status file) is
        # compared with the requested one; 'already running' is said only when it covers these run/days
        status, _ = worker_state(line)
        theirs = (status or {}).get('scope')
        try:
            covered = bool(theirs) and parse_scope(theirs)['run'] == scope['run'] and \
                set(scope['days']) <= set(parse_scope(theirs)['days'])
        except SystemExit:
            covered = False
        with locked():
            event(line, 'kick_worker_running', by=by, worker=(status or {}).get('pid'), scope=scope['text'],
                  worker_scope=theirs, covered=covered)
        return dict(started=False, covered=covered, worker_scope=theirs,
                    reason='a %s worker runs (pid %s, scope %s): it %s; days outside its scope wait for the next kick '
                           'after it ends' % (line, (status or {}).get('pid'), theirs,
                                              'covers %s' % scope['text'] if covered else 'does NOT cover %s' % scope['text']))
    probe.close()                         # released: the new worker takes it (a race with another kick: one of them exits)
    (QUEUE / 'logs').mkdir(parents=True, exist_ok=True)
    log_path = QUEUE / 'logs' / ('%s-worker.log' % line)
    argv = [sys.executable, '-B', str(HERE / 'frankie_box_frankie_queue.py'), '--action', 'worker', '--line', line,
            '--code-root', str(code_root), '--commit', commit, '--max-seconds', str(int(max_seconds)),
            '--poll-seconds', str(int(poll_seconds)), '--scope', scope['text']]
    env = dict(PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1', PYTHONPATH=str(code_root), HOME=os.environ.get('HOME') or '/root',
               MARKETS_SHA=commit, CODE_ROOT=str(code_root), **_run_settings_env())
    how = None
    if shutil.which('systemd-run'):
        unit = 'frankie-queue-%s-%d' % (line, int(time.time()))
        cmd = ['systemd-run', '--unit', unit, '--collect', '-p', 'StandardOutput=append:%s' % log_path,
               '-p', 'StandardError=append:%s' % log_path,
               '-p', 'KillMode=mixed',   # S2 (stacks pass 2026-10-07): a stop signals the MAIN process only (its save route marks and runs
               # to the save point); the stages' pool workers are not SIGTERMed under it (the default control-group mode did, and a
               # parent redid their work with one fewer before its save point); the remainder is SIGKILLed at TimeoutStopSec
               ] + [x for k, v in sorted(env.items()) for x in ('-E', '%s=%s' % (k, v))] + argv
        code = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).returncode
        how = dict(method='systemd-run', unit=unit, exit_code=code)
    if how is None or how['exit_code'] != 0:
        with open(log_path, 'ab') as out:
            proc = subprocess.Popen(argv, env=dict(os.environ, **env), stdout=out, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, start_new_session=True)
        how = dict(method='new session', pid=proc.pid, systemd_run=how)
    # B3a (2026-10-07): the kick is recorded BEFORE it returns (<line>-kick.json: when, by, scope, how) and waits, bounded,
    # until the new worker holds its lock, so a caller's KeepRunning clear (box_in_use) never sees an idle box while the
    # kicked worker is still importing; a worker that has not taken its lock in time is named, and the kick marker keeps
    # the box in use for KICK_GRACE_SECONDS
    import frankie_box_cores as C
    settings = _run_settings_env()
    cpu_watch = _start_cpu_watch(code_root, log)      # session 8: the watchdog loop rides every kick (idempotent)
    C.write_json(QUEUE / ('%s-kick.json' % line), dict(schema='FRANKIE_QUEUE_KICK_V1', line=line, at=time.time(), at_utc=utc(),
                                                       by=by, scope=scope['text'], how=how, run_settings=settings, cpu_watch=cpu_watch))
    deadline, held = time.time() + KICK_LOCK_WAIT_SECONDS, False
    while time.time() < deadline:
        _, held = worker_state(line)
        if held:
            break
        time.sleep(1.0)
    with locked():
        event(line, 'kick', by=by, commit=commit, code_root=str(code_root), max_seconds=max_seconds, how=how, log=str(log_path),
              scope=scope['text'], worker_lock_held=bool(held), run_settings=settings, cpu_watch=cpu_watch)
    log('%s worker started for %s (%s); log %s; worker lock %s' % (line, scope['text'], how, log_path,
                                                                  'held' if held else 'NOT yet held after %d s' % KICK_LOCK_WAIT_SECONDS))
    return dict(started=True, how=how, log=str(log_path), scope=scope['text'], worker_lock_held=bool(held),
                run_settings=settings, cpu_watch=cpu_watch)


def handover(line, code_root, commit, max_seconds, poll_seconds, log=print, scope=None):
    """Move the line to new code without stopping any running day (2026-09-30): the running worker gets SIGTERM, which
    only stops it TAKING new work (its running days finish in their slots, then it ends and releases its lock); a new
    worker at this commit starts detached now and waits on the lock, so it takes over the moment the old one ends. The
    new worker carries the given scope (never the old worker's, never wider)."""
    scope = parse_scope(scope)
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
    # an earlier handover's worker still WAITING on the lock (it never took it, so it runs nothing) is ended: only the
    # newest code takes over
    superseded = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name) in (os.getpid(), signalled):
            continue
        try:
            c = (proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
        except OSError:
            continue
        if 'frankie_box_frankie_queue.py' in c and '--line root' in c and '--wait-lock' in c:
            try:
                os.kill(int(proc.name), signal.SIGTERM)
                superseded.append(int(proc.name))
            except OSError:
                pass
    (QUEUE / 'logs').mkdir(parents=True, exist_ok=True)
    log_path = QUEUE / 'logs' / ('%s-worker.log' % line)
    argv = [sys.executable, '-B', str(HERE / 'frankie_box_frankie_queue.py'), '--action', 'worker', '--line', line,
            '--code-root', str(code_root), '--commit', commit, '--max-seconds', str(int(max_seconds)),
            '--poll-seconds', str(int(poll_seconds)), '--wait-lock', '--scope', scope['text']]
    env = dict(PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1', PYTHONPATH=str(code_root), HOME=os.environ.get('HOME') or '/root',
               MARKETS_SHA=commit, CODE_ROOT=str(code_root), **_run_settings_env())
    unit = 'frankie-queue-%s-handover-%d' % (line, int(time.time()))
    cmd = ['systemd-run', '--unit', unit, '--collect', '-p', 'StandardOutput=append:%s' % log_path,
           '-p', 'StandardError=append:%s' % log_path,
           '-p', 'KillMode=mixed'] + [x for k, v in sorted(env.items()) for x in ('-E', '%s=%s' % (k, v))] + argv   # S2: as kick()
    code = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).returncode
    with locked():
        event(line, 'handover', old_pid=old, signalled=signalled, superseded=superseded, unit=unit, exit_code=code,
              commit=commit, scope=scope['text'], run_settings=_run_settings_env())
    return dict(old_worker=old, signalled=signalled, superseded_waiting=superseded, new_unit=unit, systemd_run_exit=code, log=str(log_path),
                note='the old worker finishes the days in its slots and ends; the new one waits on the lock, then runs')


# FA-6 (2026-10-07): the run settings of the kicking process (every FRANKIE_* variable, e.g.
# FRANKIE_ROOT_NATIVE_OVERLAP) reach the worker it starts and so the stages it runs; recorded in the kick receipt. Never
# passed: the per-process identity a parent sets for its own child (lane, booking, claim, heartbeat file), which a worker
# must take from its own claim, and anything named like a credential.
RUN_SETTING_PREFIX = 'FRANKIE_'
RUN_SETTING_IDENTITY = ('FRANKIE_LANE_', 'FRANKIE_BOOKED_CPUS', 'FRANKIE_CPU_BOOKING', 'FRANKIE_STEP_CLAIM',
                        'FRANKIE_STAGE_PROGRESS', 'FRANKIE_PROBE_DIRS')   # FRANKIE_PROBE_DIRS: a stage child's own probe
                                        # directories (frankie_box_experiment.Run.child), never a run setting
RUN_SETTING_SECRET = re.compile(r'TOKEN|SECRET|PASSWORD|CREDENTIAL|(^|_)KEY($|_)')


def _run_settings_env():
    """{name: value} of the kicking process's FRANKIE_* run settings (see RUN_SETTING_*). FRANKIE_ROOT_NATIVE_OVERLAP
    is passed only as on | off (frankie_box_experiment_root.sh refuses anything else); a value holding a newline or NUL is
    never passed (systemd-run -E cannot carry it)."""
    out = {}
    for name, value in sorted(os.environ.items()):
        if not name.startswith(RUN_SETTING_PREFIX) or name.startswith(RUN_SETTING_IDENTITY) or RUN_SETTING_SECRET.search(name):
            continue
        if '\n' in value or '\0' in value:
            continue
        if name == 'FRANKIE_ROOT_NATIVE_OVERLAP' and value not in ('on', 'off'):
            continue
        out[name] = value
    return out


def _entry_running(entry):
    """A day whose work may be live: the entry or its finish is running, or its state is unknown (an owner gone without
    an acknowledgment: possibly still running). Such a day never changes source."""
    finish = (entry.get('finish') or {}).get('state')
    return entry.get('state') in ('running', 'unknown') or finish in ('running', 'unknown')


def _source_wait(entry, code_root, commit):
    """Admission source check (called under the queue lock). Greg, 2026-10-07: "The box is going to follow the days
    around as it moves through the workflow": a day that is NOT running (saved, resumed, queued, failed or waiting)
    follows the worker's current source; the change is recorded on the entry (source_rebinds: old and new commit and
    code_root, when, the rule) and on its owner binding (owner.source_history), the old binding kept. The day's own
    stage resume checks still decide (ROOT's legacy/input identities, the classroom's phase keys, ...): a stage that
    refuses the new code refuses visibly, as before. A RUNNING (or unknown) day never moves: it waits with the reason."""
    owner = entry.get('source_owner')
    expected = dict(commit=commit, code_root=str(Path(code_root).resolve()))
    if owner is None:
        if (entry.get('attempts') or entry.get('finish')) and _entry_running(entry):
            return 'a running day has no source-owner binding; it never changes source while it runs'
        return None
    if owner != expected:
        if _entry_running(entry):
            return ('the day is running (or unknown) on its source %s; a running day never moves to another source (save it '
                    'first; a saved day follows the current source on its next admission)' % owner.get('commit'))
        if not Path(expected['code_root']).is_dir():
            return 'this worker\'s checkout %s is unavailable; the day keeps its source %s' % (
                expected['code_root'], owner.get('commit'))
        record = dict(at_utc=utc(), at=time.time(), previous=dict(owner), new=dict(expected), pid=os.getpid(),
                      state=entry.get('state'), finish=(entry.get('finish') or {}).get('state'),
                      rule='a day that is not running follows the current source (Greg, 2026-10-07); its stages\' own '
                           'resume identity checks still decide')
        entry.setdefault('source_rebinds', []).append(record)
        entry['source_owner'] = dict(expected)
        if isinstance(entry.get('owner'), dict) and (entry['owner'].get('commit'), entry['owner'].get('code_root')) != \
                (expected['commit'], expected['code_root']):
            history = list(entry['owner'].get('source_history') or [])
            history.append(dict(commit=entry['owner'].get('commit'), code_root=entry['owner'].get('code_root'),
                                until_utc=record['at_utc']))
            entry['owner'] = dict(entry['owner'], commit=expected['commit'], code_root=expected['code_root'],
                                  source_history=history)
        return None
    if not Path(owner['code_root']).is_dir():
        return 'retained day checkout is unavailable; restore its original source before resume'
    return None


def _bind_source(entry, code_root, commit):
    """Called under the queue lock only after _source_wait allows admission."""
    if entry.get('source_owner') is None:
        entry['source_owner'] = dict(commit=commit, code_root=str(Path(code_root).resolve()))


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
    run = X.Run(a, plan, code_root, commit, log=log)
    run.source_owner = entry.get('source_owner')
    run.bind_owner(entry.get('owner'))
    return run, e


class Bound(BaseException):
    """The class worker's time bound or a stop signal: save and end (a BaseException, so no step's own except Exception
    records it as the step's failure)."""


def _signal_bound(*_):
    raise Bound('stopped by a signal')


# ------------------------------------------------------------------------------------------------------ class line

def previous_for(doc, entry, plan):
    """The class the entry carries: (directory or None, None, where it came from, record)."""
    import frankie_box_experiment as X
    if 'previous' in entry:
        # Resume the selected class, including an explicit empty bootstrap. Never repick after a save.
        prior = entry['previous']
        return prior.get('classroom'), None, entry['previous_from'], prior
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
    if r and stage in ('exchange', 'voice', 'school', 'reports'):
        run.require_current_teacher_inputs(day)
    if not r:
        return False
    if stage == 'classroom':
        return r['status'] in ('done', 'reused')
    if stage == 'school':
        return run.finished('school', day)       # school currentness: a checked successor makes a done school run again
    if stage == 'voice':
        # a non-blocking meeting state passes: the runtime gate's refusal, inputs-only, a runtime failure, or the remote
        # route's pending dispatch/admission/return (Run.voice_remote); the reports are rebuilt when the meeting arrives
        return r['status'] in X.FINISHED or bool(r['status'] == 'waiting' and r.get('non_blocking')
                                                and r.get('meeting_status') in ('refused', 'inputs_only', 'runtime_failed',
                                                                                'remote_pending'))
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
    s = run.receipt('search', day)
    if not (s and s['status'] in X.FINISHED):
        return run.record('frankie_lessons', day, 'waiting', reason='the day\'s search is %s (Frankie\'s claims are tested '
                                                                    'on the searches)' % ((s or {}).get('status') or 'not run'))
    if s['status'] == 'not_run':
        # no causal axis on this day (the search is a listed not_run): Frankie's claims of the day cannot be tested on
        # its own search; listed, the day goes on (the missing operand blocks this equation only)
        return run.record('frankie_lessons', day, 'skipped', reason='the day\'s search is not_run (%s): no search of the '
                                                                    'day to test Frankie\'s claims on; listed' % s.get('reason'))
    # a not_run search of another day supplies no search either: never passed as a path to the teacher
    searched = [x['day'] for x in run.plan['days'] if x['role'] == 'discovery' and run.finished('search', x['day'])
                and (run.receipt('search', x['day']) or {}).get('status') != 'not_run']
    remote = [d for d in searched if run.remote_root(d)]
    if remote:
        return run.record('frankie_lessons', day, 'waiting', remote_days=remote,
                          reason='each remote search needs its owning lane scientific result; local paths cannot cover it')
    try:
        written = run.lessons_written('frankie-%s' % day, searched, frankie_ledgers=ledgers)
    except (ValueError, OSError) as error:
        return run.record('frankie_lessons', day, 'waiting', requested_search_days=searched, reason=str(error))
    if written:
        import frankie_box_scientific_teacher as ST
        for path in written:
            ST.publish_lessons(path, brain_dir=run.plan.get('brain') or str(X.BRAIN), log=run.log)
        return run.record('frankie_lessons', day, 'reused', searched_days=searched, lessons=[str(w) for w in written])
    searches = ','.join(str(X.SEARCH / d / ('cycle-' + X.CYCLE) / 'discovery') for d in searched)
    # a lessons call is a day-run step: run as stage 'lessons' so it books its 16 CPUs in the ledger like the batch calls
    code, log = run.child('lessons', day, 'frankie_box_scientific_teacher.sh',
                          dict(FRANKIE_LEDGERS=ledgers, FRANKIE_DAY=day, SEARCHES=searches,
                               BRAIN=run.plan.get('brain') or str(X.BRAIN)))
    cpu = getattr(run, '_cpu', {}).pop(('lessons', day), None)
    try:
        written = run.lessons_written('frankie-%s' % day, searched, frankie_ledgers=ledgers)
    except (ValueError, OSError) as error:
        return run.record('frankie_lessons', day, 'waiting', exit_code=code, log=log, cpu_booking=cpu,
                          requested_search_days=searched, reason=str(error))
    if cpu and cpu['status'] == 'waiting' and not written:
        return run.record('frankie_lessons', day, 'waiting', exit_code=code, log=log, cpu_booking=cpu, reason=cpu['line'])
    if code != 0 or not written:
        return run.record('frankie_lessons', day, 'failed', exit_code=code, log=log, searched_days=searched, cpu_booking=cpu,
                          reason=(cpu or {}).get('line') if (cpu or {}).get('status') == 'refused' else
                          'no FRANKIE_LESSONS_V1 of the day after the call (its log names why)')
    return run.record('frankie_lessons', day, 'done', exit_code=code, log=log, searched_days=searched,
                      lessons=[str(w) for w in written], cpu_booking=cpu)


def class_day(entry, previous, school_day, code_root, commit, log):
    """Run one classroom-arm day inside the SAME held 16-CPU slot.

    Canonical order (Greg, settled 2026-09-30; reconciled 2026-10-06):
      classroom immediately after the BOSS teacher read -> data export -> search -> batch scientific-teacher lessons
      -> today's Frankie findings tested -> three-way exchange -> bounded meeting -> school -> reports.

    The classroom is deliberately before search: Frankie first learns from ROOT + the BOSS teacher.  The later
    scientific-teacher pass tests his resulting claims against the causal search before the meeting.  Nothing here
    releases or re-books the day's slot.
    """
    why = _source_wait(entry, code_root, commit)
    if why:
        return 'waiting', why, {}
    if not _slot_live(entry.get('slot_booking')):
        return 'waiting', 'the owning day has no live held slot; owner recovery required before class work', {}
    run, e = _run_for(entry, code_root, commit, log)
    day = e['day']
    run.slot_booking = entry['slot_booking']
    run.successors(day)
    run.check_save()
    run.school_day = school_day
    run.queue_previous = previous[:3]
    facts = dict(stages={})

    def keep(stage, r, receipt_stage=None, receipt_key=None):
        run.successors(day)
        receipt_stage = receipt_stage or stage
        receipt_key = receipt_key or day
        facts['stages'][stage] = dict(status=r['status'], reason=r.get('reason'),
                                      receipt=str(run.receipt_path(receipt_stage, receipt_key)))
        if r['status'] == 'waiting' and not passed(run, receipt_stage, receipt_key):
            return 'waiting', '%s: %s' % (stage, r.get('reason'))
        if not passed(run, receipt_stage, receipt_key):
            if stage == 'classroom' and r['status'] == 'refused':
                rep = run.guarded('reports', e)
                facts['stages']['reports'] = dict(status=rep['status'], reason=rep.get('reason'),
                                                  receipt=str(run.receipt_path('reports', day)))
            return 'failed', '%s %s: %s' % (stage, r['status'], r.get('reason'))
        # session 6: the stage-boundary sequence after every passed class-side step (validate -> save -> clean ->
        # trigger); the class worker stops on the owner's marker it shares (its acknowledgment follows, unchanged)
        if _boundary(run, e, receipt_stage, receipt_key, run.receipt(receipt_stage, receipt_key), code_root, commit, log, facts):
            return 'failed', '%s: handoff failed: %s' % (stage, (facts.get('handoff') or {}).get(receipt_stage, {}).get('reason'))
        run.check_save()
        return None, None

    # 1. Frankie learns immediately after the BOSS teacher's read.
    if passed(run, 'classroom', day):
        r = run.receipt('classroom', day)
    else:
        r = run.classroom(e)
        if r is None:
            why = (run.stopped or {}).get('reason')
            run.stopped = None
            return 'waiting', 'classroom: %s' % why, facts
        run.reserve_after_classroom(e)
    state, why = keep('classroom', r)
    if state:
        return state, why, facts

    # 2. Build/search the causal evidence only after Frankie's classroom work exists.
    for stage in ('data', 'search'):
        if passed(run, stage, day):
            r = run.receipt(stage, day)
        else:
            r = run.guarded(stage, e)
            if r is None:
                why = (run.stopped or {}).get('reason')
                run.stopped = None
                return 'waiting', '%s: %s' % (stage, why), facts
        state, why = keep(stage, r)
        if state:
            return state, why, facts

    # 3. Test prior/historical/Jev claims on the searches available so far.
    key = run.batch_of(day)
    if key and key.startswith('discovery') and not run.finished('lessons', key):
        run.check_save()
        batch = [d for d in run.plan['days'] if run.batch_of(d['day']) == key]
        r = run.lessons(key, batch) or {}
    else:
        r = run.receipt('lessons', key) if key else None
        if r is None:
            r = dict(status='skipped', reason='no discovery batch for this day')
    if key:
        state, why = keep('batch_lessons', r, 'lessons', key)
        if state:
            return state, why, facts
    else:
        facts['stages']['batch_lessons'] = dict(status=r['status'], reason=r.get('reason'), receipt=None)

    # 4. Test this day's new Frankie findings against the search.
    if passed(run, 'frankie_lessons', day):
        r = run.receipt('frankie_lessons', day)
    else:
        run.check_save()
        r = frankie_lessons(run, e)
    state, why = keep('frankie_lessons', r)
    if state:
        return state, why, facts

    # 5. Only now do the teachers and Frankie meet; then retain the day.
    for stage in ('exchange', 'voice', 'school', 'reports'):
        if passed(run, stage, day):
            r = run.receipt(stage, day)
        else:
            r = run.guarded(stage, e)
            if r is None:
                why = (run.stopped or {}).get('reason')
                run.stopped = None
                return 'waiting', '%s: %s' % (stage, why), facts
        state, why = keep(stage, r)
        if state:
            return state, why, facts

    facts['classroom'] = run.receipt('classroom', day).get('classroom')
    return 'done', None, facts


def _plan_of(run_name):
    import frankie_box_experiment as X
    path = X.RUNS / run_name / 'plan.json'
    return json.loads(path.read_bytes()) if path.is_file() else {}


def _write_ack(marker, ack):
    """The class child's acknowledgment beside the marker, create-only (<marker>.class-ack.json); never overwritten."""
    if not marker:
        return
    import frankie_box_cores as C
    try:
        C.write_json(Path(str(marker) + '.class-ack.json'), ack, exclusive=True)
    except FileExistsError:
        return


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


def class_worker(code_root, commit, max_seconds, poll_seconds, log=print, scope=None):
    """The one class worker: the front of the class line, one day at a time, polled while it waits; FOR its scope only."""
    scope = parse_scope(scope)
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
                   poll_seconds=poll_seconds, started_utc=utc(), scope=scope['text'])

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
                    _worker_status('class', state=state, commit=commit, front=about, scope=scope['text'])
                    event('class', 'worker_end', state=state, front=about)
                    probe.update('class:' + state, n_done, len(doc['entries']) or None,
                                 state='complete' if x is None else 'failed')
                    release()
                    code = 0 if x is None else 3
                    break
                if not in_scope(x, scope):
                    # the front is outside this worker's authorization: FIFO makes everything behind it wait, and this
                    # worker never starts it (left exactly as it is); a kick with the right scope takes it
                    about = dict(seq=x['seq'], day=x['day'], run=x['run'], state=x['state'], scope=scope['text'])
                    _worker_status('class', state='waiting_out_of_scope', commit=commit, front=about, scope=scope['text'])
                    event('class', 'worker_end', state='waiting_out_of_scope', front=about, scope=scope['text'])
                    probe.update('class:waiting_out_of_scope', n_done, len(doc['entries']) or None, state='waiting')
                    release()
                    return 5
                if (x.get('readiness') or {}).get('remote'):
                    # The remote holder runs the class in its original lane; the main worker never takes it.
                    release()
                    return 0
                if x['state'] in OWNER_STATES:
                    # the front is a saved/unknown class: its owner's ACTION=resume brings it back; nothing takes it
                    x['reason'] = 'the class is %s on its owner; ACTION=resume RUN=%s DAY=%s resumes it' % (x['state'], x['run'], x['day'])
                    save('class', doc)
                    _worker_status('class', state='waiting_owner', commit=commit, scope=scope['text'],
                                   front=dict(seq=x['seq'], run=x['run'], day=x['day'], reason=x['reason']))
                    probe.update('class:waiting_owner', n_done, len(doc['entries']) or None, state='waiting')
                    event('class', 'waiting_owner', seq=x['seq'], run=x['run'], day=x['day'], reason=x['reason'])
                    release()
                    return 5
                why = _source_wait(x, code_root, commit)
                if why is None and not _slot_live(x.get('slot_booking')):
                    why = 'the owning day has no live held slot; waiting for its owner'
                if why:
                    x['reason'] = why
                    save('class', doc)
                    _worker_status('class', state='waiting_owner', commit=commit, scope=scope['text'],
                                   front=dict(seq=x['seq'], run=x['run'], day=x['day'], reason=why))
                    probe.update('class:waiting_owner', n_done, len(doc['entries']) or None, state='waiting')
                    event('class', 'waiting_owner', seq=x['seq'], run=x['run'], day=x['day'], reason=why)
                    release()
                    return 5
                mine = (x['state'] == 'running' and x['seq'] == current and
                        (x.get('attempts') or [{}])[-1].get('pid') == os.getpid())
                if not mine:
                    if time.monotonic() >= deadline:
                        raise Bound('the time bound (%d s) before taking seq %d' % (max_seconds, x['seq']))
                    if x['state'] == 'failed':
                        retried.add(x['seq'])            # a failed front is retried once per worker start, never skipped
                    _bind_source(x, code_root, commit)
                    save('class', doc)                   # source intent precedes report/attempt side effects
                    previous, why = _take_class(doc, x, commit)
                    save('class', doc)
                    if previous is None:
                        event('class', 'failed', seq=x['seq'], day=x['day'], run=x['run'], reason=why)
                        retried.add(x['seq'])
                        continue
                    current = x['seq']
                entry = dict(x)
            _worker_status('class', state='running', commit=commit, scope=scope['text'],
                           front=dict(seq=entry['seq'], day=entry['day'], run=entry['run'], school_day=entry.get('school_day')))
            probe.update('class:%s:%s' % (entry['day'], entry['run']), n_done, len(doc['entries']) or None, in_flight=1)
            try:
                result, reason, facts = class_day(entry, previous, entry['school_day'], code_root, commit, log)
            except SystemExit as error:
                owner = entry.get('owner') or {}
                if error.code == 75 and owner.get('marker') and Path(owner['marker']).is_file():
                    # the class child saved on the owning day's marker: the ACKNOWLEDGMENT, bound to that marker, this
                    # child, the held booking and the owner's attempt; written beside the marker and on the entry
                    result, reason, facts = 'saved', 'saved on the owner\'s marker %s' % owner['marker'], {}
                else:                                    # any other refusal is the day's failure (retried once)
                    result, reason, facts = 'failed', 'SystemExit: %s' % error, {}
            except Exception as error:  # noqa: BLE001   # recorded on the entry; the line stops there (retried once)
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
                if result == 'saved':
                    owner = y.get('owner') or {}
                    ack = dict(schema='FRANKIE_QUEUE_SAVE_ACK_V1', run=y['run'], day=y['day'], marker=owner.get('marker'),
                               request=marker_identity(owner.get('marker')),      # the save this answers (its generation)
                               root_attempt=owner.get('attempt'), booking=y.get('slot_booking'), cpus=owner.get('cpus'),
                               source_owner=y.get('source_owner'), child_pid=os.getpid(),
                               child_attempt={k: att.get(k) for k in ('pid', 'host', 'started_utc', 'school_day')},
                               school_day=y.get('school_day'), stages=facts.get('stages'), at=time.time(), at_utc=utc())
                    _end_attempt(y, 'saved', reason)
                    y.update(state='saved', reason=reason, save_ack=ack)
                    save('class', doc)
                    _write_ack(owner.get('marker'), ack)
                    event('class', 'saved', seq=y['seq'], day=y['day'], run=y['run'], ack=ack)
                    log('class seq %d %s (%s): saved on its owner\'s marker; acknowledged (school day %s kept)' % (
                        y['seq'], y['day'], y['run'], y.get('school_day')))
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
            _worker_status('class', state='saved', reason=str(stop), commit=commit, scope=scope['text'])
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
        started = x['state'] in ('running', 'done') + OWNER_STATES or (claims.active() and claims.holder(x['run'], x['day']))
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


def _book_slot(x, stage, commit):
    """The day's slot (Greg, 2026-09-30: "once the day enters a pod or box it doesn't leave until the entire work flow is
    over"): EXACTLY 16 CPUs booked once in the core ledger, held by this worker process for the whole day (ROOT, teacher,
    data, search, lessons, the class, Jev); every step runs inside it (frankie_box_cores.py run --inside) and nothing
    re-books between steps, so no other day can take the CPUs while the day is between two steps. A day with an owner
    binding (a resume) books EXACTLY its retained CPU set, or the set it was grown to (same booking id): the ledger hands
    the owner its retained booking back and nobody else (session 9; _bind_owner then records the grown set). Returns
    (booking id, cpus, None) or (None, None, the ledger's waiting/refused reason)."""
    import frankie_box_cores as C
    cpus = (x.get('owner') or {}).get('cpus') or x.get('cpus')
    # the run's day slot size (plan day_cpus: 32 = both main-box lanes as one booking; default 16)
    size = int(_plan_of(x['run']).get('day_cpus') or C.DAY_RUN_CPUS)
    b, outcome = C.book('day-run', os.getpid(), dict(day=x['day'], run=x['run'], stage='day-slot-' + stage, commit=commit,
                                                  cpus=cpus, size=size), 1.0)
    return (b['booking'], b['cpus'], None) if b else (None, None, outcome.get('reason'))


def marker_of(run, day):
    return SAVE_DIR / ('%s-%s.save-request.json' % (run, day))


def marker_identity(marker):
    """The standing save request's identity: the sha256 of the marker's bytes and its requested_at (the generation).
    None when no marker stands. An acknowledgment carries the identity it answered; a verdict compares it with the
    marker standing NOW, so an earlier save's acknowledgment never satisfies a later save."""
    if not marker or not Path(marker).is_file():
        return None
    raw = Path(marker).read_bytes()
    try:
        requested_at = json.loads(raw).get('requested_at')
    except ValueError:
        requested_at = None
    return dict(sha256=hashlib.sha256(raw).hexdigest(), requested_at=requested_at)


def _bind_owner(x, slot, cpus, code_root, commit):
    """Under the queue lock, BEFORE the day's thread starts: the owner binding the day keeps for its whole life (a resume
    reuses every field; a new attempt is never minted for an owned day). The attempt is the exact ROOT directory name:
    a completed ROOT's, else the next number after the interrupted attempts of the day."""
    import frankie_box_experiment as X
    owner = x.get('owner')
    if owner is None:
        plan = _plan_of(x['run'])
        e = next((d for d in plan.get('days') or [] if d['day'] == x['day']), None)
        calc, attempts = X.root_of(e, x['run']) if e is not None else (None, [])   # a refusal is the caller's to record
        attempt = calc.name if calc is not None else '%s-%s-a%d' % (x['run'], x['day'], len(attempts) + 1)
        owner = dict(schema='FRANKIE_QUEUE_OWNER_V1', run=x['run'], day=x['day'], host=socket.gethostname(),
                     attempt=attempt, commit=commit, code_root=str(Path(code_root).resolve()),
                     marker=str(marker_of(x['run'], x['day'])), bound_utc=utc(), bound_by_pid=os.getpid())
        released = x.pop('failed_finish_bookings', None)
        if released:
            why_not = _jev_progress(x['run'], x['day'])
            decision = dict(by='queue-after-failed', at_utc=utc(), previous_booking=released.get('booking'),
                            previous_cpus=released.get('cpus'), held_bookings=released.get('held_bookings') or [],
                            released_attempt=released.get('attempt'), released_why=released.get('why'),
                            rule='the retry of a FAILED finish on a new booking: the released owner\'s bookings, so a retained '
                                 'Jev request with no progress gets its create-only .rebookN successor (the original '
                                 'request never changed)')
            if why_not is None:
                owner['rebooked'] = decision
                x.setdefault('owner_rebooks', []).append(decision)
            else:
                x.setdefault('owner_rebooks', []).append(dict(decision, not_applied=why_not))
    # held_bookings: every booking this SAME owner binding (attempt, marker) has held, in order. A queue rebook decision
    # (_rebook_owner) carries it, so a Jev request bound to any earlier booking of this owner has its explicit REBOOK
    # successor (Run.jev_rebooked) instead of a refusal (second review F1)
    held = list(owner.get('held_bookings') or [])
    held.append(dict(booking=slot, cpus=sorted(cpus), bound_utc=utc()))
    if owner.get('cpus') and sorted(owner['cpus']) != sorted(cpus):
        # session 9 (Greg's CPU add before a resume): the retained booking was GROWN; the owner binding records the
        # booking's actual set from here on (re-books between steps, resume/status readouts), the old set kept
        owner = dict(owner, cpus_before_grow=sorted(owner['cpus']))
    owner = dict(owner, cpus=sorted(cpus), booking=slot, holder_pid=os.getpid(), holder_utc=utc(), held_bookings=held)
    x['owner'] = owner
    import frankie_box_cores as C
    C.own(slot, x['run'], x['day'], owner['attempt'])       # the ledger: this booking's death retains it for this owner
    return owner


def _release_slot(booking, reason):
    import frankie_box_cores as C
    try:
        C.release(booking, reason)
    except (OSError, ValueError) as error:          # the ledger's reap releases it once this worker is gone
        print('slot %s not released now (%s); reaped when its holder ends' % (booking, error), flush=True)


def _slot_live(booking):
    import frankie_box_cores as C
    return bool(booking) and C.held_booking(booking)[0] is not None


def _after_root(run, e, code_root, commit, log):
    """A finished ROOT of a line day: an arm day whose teacher rows are there enters the class line at once (the
    classroom step's own readiness checks), and the class worker is kicked. Returns what happened, for the entry."""
    if not (e['classroom_arm'] and getattr(run.a, 'frankie_queue', 'on') == 'on') or run.finished('classroom', e['day']):
        return None
    c = run.enqueue_classroom(e)
    out = dict(status=(c or {}).get('status'), seq=(c or {}).get('queue_seq'), reason=(c or {}).get('reason'))
    slot = getattr(run, 'slot_booking', None)
    if slot:
        with locked():                              # the class runs inside the day's own held slot (no second booking)
            doc = load('class')
            y = next((z for z in doc['entries'] if z['run'] == run.plan['run'] and z['day'] == e['day']), None)
            if y is not None and y['state'] != 'done':
                source_owner = getattr(run, 'source_owner', None)
                if y.get('source_owner') is not None and y['source_owner'] != source_owner:
                    out.update(status='waiting', owner_waiting=True,
                               reason='class entry source differs from its owning day; explicit recovery required')
                    return out
                owner = getattr(run, 'owner', None)
                if y.get('owner') is not None and owner is not None and \
                        (y['owner'].get('attempt'), y['owner'].get('marker')) != (owner.get('attempt'), owner.get('marker')):
                    out.update(status='waiting', owner_waiting=True,
                               reason='class entry owner binding differs from its owning day; explicit recovery required')
                    return out
                y['slot_booking'] = slot
                if source_owner is not None:
                    y['source_owner'] = source_owner
                if owner is not None:
                    y['owner'] = dict(owner, booking=slot)     # the same marker, attempt and CPUs as the owning day
                save('class', doc)
                event('class', 'slot', seq=y['seq'], day=y['day'], run=y['run'], slot_booking=slot, owner=y.get('owner'))
    if (c or {}).get('status') == 'queued':
        kick('class', code_root, commit, run.a.queue_worker_seconds, run.a.queue_poll_seconds,
             by='ROOT line after %s %s' % (run.plan['run'], e['day']), log=log, scope=run.scope_text())
    return out


TEACHER_BOOK_WAIT = 1800        # seconds the teacher retries a CPU booking (only when the day holds no slot)


def _finish_day(run, e, code_root, commit, log):
    """Finish a day in the SAME held 16-CPU slot: _finish_steps, then the one-day inspection reporter.

    Returns (finished, facts). facts['finish'] is 'finished', 'waiting' (the day stopped at a step that waits: the entry
    records waiting, retried once per worker start, never a failure) or 'failed' (a refusal or a failed child: the entry
    records failed with the step's reason). facts['inspection'] is the reporter's receipt (frankie_box_experiment.Run.
    inspect_day): one markdown per workflow piece under days/<day>/inspection plus index.md, written after the day's
    last step here WHATEVER the outcome, including a save (Greg, 2026-10-07: see how each piece ran before the THREE-day
    run). Never a gate: a reporter failure is recorded, the day's outcome stands.
    """
    try:
        status, facts = _finish_steps(run, e, code_root, commit, log)
    except SystemExit as error:
        if error.code == 75 and run.save_requested():
            saved = dict(getattr(run, 'save_facts', None) or {})
            saved['inspection'] = _inspect(run, e['day'], 'saved', log)
            run.save_facts = saved
        else:
            # F3: any other SystemExit (a refusal raised as SystemExit) still gets the day's inspection, then propagates
            _inspect(run, e['day'], 'failed (%s: %s)' % (type(error).__name__, error), log)
        raise
    except Exception as error:
        # F3 (second review): a step that raises (close_day refusing a successor off its lane, the teacher raising) is
        # exactly the day an operator needs to see: the inspection runs, then the error propagates to the thread's one
        # classification (_thread_end: finish_failed with the reason), unchanged
        _inspect(run, e['day'], 'failed (%s: %s)' % (type(error).__name__, error), log)
        raise
    facts['finish'] = status
    facts['inspection'] = _inspect(run, e['day'], status, log)
    return status == 'finished', facts


def _inspect(run, day, outcome, log):
    """The reporter after the day's last step on this lane; never raises, never fails the day. Only for the one-day
    test plan (Run.inspection_on: plan['inspection'] == 'one_day'; Greg 2026-10-07); otherwise None (the skip is logged
    once by the Run, nothing per day)."""
    try:
        if not run.inspection_on():
            return None
        return run.inspect_day(day, 'queue line: the day ended %s on its held slot' % outcome)
    except BaseException as error:  # noqa: BLE001 - the reporter is operator review, never the day's outcome
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        log('inspection %s %s: not written (%s: %s)' % (run.plan['run'], day, type(error).__name__, error))
        return dict(status='failed', reason='%s: %s' % (type(error).__name__, error))


def _boundary(run, e, stage, key, record, code_root, commit, log, facts):
    """Session 6 (Greg, 2026-10-08): the one stage-boundary sequence after a finished step, every piece alike
    (frankie_box_stage_handoff.boundary: validate every pinned artifact once on the lane -> request the day's own save
    marker -> the detached clean on the retained lane -> its trigger resumes and kicks the day on the launching
    checkout). Returns 'failed' when validation failed (the successor never starts on unvalidated data), else None;
    the caller's next run.check_save() honours the save requested here (exit 75: the day saved, the stage stopped)."""
    import frankie_box_stage_handoff as H
    try:
        h = H.boundary(run, e, stage, key, record, code_root=code_root, commit=commit, log=log)
    except Exception as error:  # noqa: BLE001 - the handoff's own error is named on the day, never a silent pass
        h = dict(status='failed', reason='handoff error: %s: %s' % (type(error).__name__, error))
    facts.setdefault('handoff', {})[stage] = {k: h.get(k) for k in ('status', 'reason', 'switch', 'clean_plan', 'save', 'clean_unit')}
    if h.get('status') == 'failed':
        log('%s %s %s: handoff FAILED: %s' % (stage, run.plan['run'], e['day'], h.get('reason')))
        return 'failed'
    return None


def _finish_steps(run, e, code_root, commit, log):
    """The day's steps after its ROOT, in the held slot; (status, facts), status in finished / waiting / failed.

    ROOT has already finished.  The BOSS teacher always reads next.  On classroom-arm days Frankie then enters the
    class line immediately; that worker runs classroom -> data/search -> scientific-teacher tests -> meeting/end while
    staying inside this slot. Non-classroom days run data/search, consume accumulated scientific claims on their
    owning search and publish those lessons before any following batch work.
    Jev's blind material relay remains the final applicable handoff and never carries Frankie's answers.
    """
    import frankie_box_experiment as X
    facts = {}
    run.successors(e['day'])
    if _boundary(run, e, 'root', e['day'], run.receipt('root', e['day']), code_root, commit, log, facts):
        return 'failed', facts            # session 6: ROOT validated once on the lane; a mismatch stops the day here
    run.check_save()                      # the save the boundary requested is honoured here (ROOT stays stopped)

    # BOSS teacher: whole journal, every level, day-local rows.
    rows, source, why = run.day_rows(e)               # the one gate: rows the plan's shared policy refuses are none
    if rows is None:
        deadline = time.monotonic() + TEACHER_BOOK_WAIT
        retries = 0
        while True:
            run.check_save()
            t = run.teacher('day-%s' % e['day'], [e]) or {}
            rows, source, why = run.day_rows(e)
            if t.get('status') != 'waiting' or rows is not None or time.monotonic() > deadline:
                break
            retries += 1
            log('teacher %s %s: waiting (%s); retrying in the held slot' % (run.plan['run'], e['day'], t.get('reason')))
            time.sleep(30)
        facts['teacher'] = dict(status=t.get('status'), reason=t.get('reason'), log=t.get('log'), retries=retries,
                                waited_seconds=TEACHER_BOOK_WAIT if time.monotonic() > deadline else None)
        if rows is None and why and why.startswith('refused'):
            # the plan's shared market policy refuses the retained rows: an identity mismatch, a visible refusal (the
            # reason names the one route), never missing coverage; the day stops here with it
            facts['teacher'].update(rows=None, rows_refused=why)
            return 'failed', facts
        if rows is None:
            # THE MISSING-COVERAGE RULE (Greg, 2026-10-07): no teacher rows for the day (the teacher step failed or is
            # still waiting at the bound, or its policy wait) is thinner evidence, not a rejected day. The day goes on; each consumer records its own disposition
            # (the classroom waits on the rows it needs, the data export lists them missing and searches without them,
            # a later teacher result would be a second export of the day, declined there). Named here and on the entry.
            facts['teacher'].update(rows=None, rows_waiting=why,
                                    rows_missing='no teacher rows for the day after the teacher step ended %s%s: the day goes '
                                                 'on without them (missing-coverage rule); the classroom waits on them, the '
                                                 'data export lists them missing and a later teacher result is a second '
                                                 'export of the day (declined there)' % (
                                                     t.get('status') or 'not run',
                                                     (' (%s)' % (why or t.get('reason'))) if (why or t.get('reason')) else ''))
            log('teacher %s %s: %s' % (run.plan['run'], e['day'], facts['teacher']['rows_missing']))
        else:
            facts['teacher'].update(rows=str(rows), source=source, brain_entries=t.get('brain_entries'))
    else:
        t = run.teacher('day-%s' % e['day'], [e])
        facts['teacher'] = dict(status=t['status'], rows=str(rows), source=source,
                                brain_entries=t.get('brain_entries'))

    if _boundary(run, e, 'teacher', 'day-%s' % e['day'], run.receipt('teacher', 'day-%s' % e['day']), code_root, commit,
                 log, facts):
        return 'failed', facts
    run.check_save()

    if e['classroom_arm'] and os.environ.get('FRANKIE_LANE_MAILBOX'):
        import frankie_box_lane_state as LS
        while True:
            run.check_save()
            lease = LS.request('class_take', settings=settings_of(run.a))
            if not lease['waiting']:
                break
            time.sleep(15)
        if lease['files']:
            LS.restore_classroom_carry(lease['previous'][0], lease['files'], [X.ROOTS])
        run.check_save()
        entry = dict(run=run.plan['run'], day=e['day'], settings=settings_of(run.a),
                     plan_sha256=X.plan_digest(run.plan), slot_booking=run.slot_booking)
        state, why, class_facts = class_day(entry, lease['previous'], lease['school_day'], code_root, commit, log)
        facts['frankie'] = dict(status=state, reason=why)
        if state != 'done':
            return ('waiting' if state == 'waiting' else 'failed'), facts
        c = Path(class_facts['classroom'])
        LS.request('class_done', classroom=str(c), files=LS.pack_classroom_carry(c))
    elif e['classroom_arm']:
        # Greg's settled order: Frankie learns from ROOT + BOSS teacher BEFORE the search tests his resulting claims.
        facts['class_line'] = _after_root(run, e, code_root, commit, log)
        while True:
            if (facts.get('class_line') or {}).get('owner_waiting'):
                # An older failed class is not this owner's failure. Keep the current thread/slot and
                # original attempts while source recovery is pending; no terminal acknowledgment. A save stands on its
                # own here: the class entry is not taken by anyone while its binding disagrees (no child to acknowledge).
                if run.save_requested() and run.owner:
                    facts['child'] = dict(state='no_child_running', reason='the class entry\'s binding differs from the owning '
                                                                           'day; nobody takes it: no child to acknowledge')
                    run.save_facts = facts
                    raise SystemExit(75)
                log('class %s %s: holding its slot (%s)' % (
                    run.plan['run'], e['day'], facts['class_line']['reason']))
                time.sleep(60)
                facts['class_line'] = _after_root(run, e, code_root, commit, log)
                continue
            cl = entry_of('class', run.plan['run'], e['day'])
            state = (cl or {}).get('state')
            if state == 'queued' and not worker_state('class')[1]:
                # no class worker runs (a scoped one ended at another run's front, or at its bound): this owner kicks one
                # for its own run's scope, so its class is taken; a worker already running keeps its own scope
                kick('class', code_root, commit, run.a.queue_worker_seconds, run.a.queue_poll_seconds,
                     by='owning day %s %s (class queued, no worker)' % (run.plan['run'], e['day']), log=log, scope=run.scope_text())
            if run.save_requested() and run.owner:
                # THE CHILD ACKNOWLEDGMENT. The class runs in the class worker's process on the same marker. This owner
                # does not end as saved on its own say-so: it waits for the class entry to reach saved with an
                # acknowledgment bound to this marker, booking and attempt (or done/failed, which need no ack). A child
                # that is gone without one, or an ack bound to something else, is unknown, never acknowledged.
                verdict = _child_save_verdict(run, e, cl)
                if verdict is None:
                    log('save %s %s: requested; waiting for the class child\'s acknowledgment (class entry %s)' % (
                        run.plan['run'], e['day'], state))
                    time.sleep(15)
                    continue
                facts['frankie'] = dict(status=state, reason=(cl or {}).get('reason'), school_day=(cl or {}).get('school_day'))
                facts['child'] = verdict
                run.save_facts = facts                 # carried to the thread's result (the exception carries no facts)
                raise SystemExit(75)
            run.check_save()
            if state in ('done', 'failed') or (cl is None and run.finished('classroom', e['day'])):
                break
            if cl is None and (facts.get('class_line') or {}).get('status') not in ('queued', None):
                # the class line's door did not take the day: waiting (its classroom readiness names what it waits on,
                # the teacher rows among them) or refused; the entry records the same word, never a bare failure
                door = (facts.get('class_line') or {}).get('status')
                facts['frankie'] = dict(status=door, not_queued=True, reason=(facts.get('class_line') or {}).get('reason'))
                return ('waiting' if door == 'waiting' else 'failed'), facts
            if cl is None:
                facts['class_line'] = _after_root(run, e, code_root, commit, log)
            # the owner's poll of its class entry: 15 s (was 60), so Jev and the close start within 15 s of the class
            # ending instead of up to a minute later; one small JSON read under the queue lock per poll
            time.sleep(OWNER_CLASS_POLL)
        facts['frankie'] = dict(status=state or 'classroom finished', reason=(cl or {}).get('reason'),
                                school_day=(cl or {}).get('school_day'))
        if state == 'failed':
            return 'failed', facts
    else:
        # Search-only discovery days do not enter the class line.
        for stage in ('data', 'search', 'accumulated_lessons'):
            r = run.guarded(stage, e) or {}
            facts[stage] = dict(status=r.get('status'), reason=r.get('reason'), target=r.get('target'), log=r.get('log'))
            if r.get('status') not in X.FINISHED:
                return ('waiting' if r.get('status') == 'waiting' else 'failed'), facts
            if _boundary(run, e, stage, e['day'], r, code_root, commit, log, facts):
                return 'failed', facts
            run.check_save()
        key = run.batch_of(e['day'])
        if key and key.startswith('discovery') and not run.finished('lessons', key):
            run.check_save()
            batch = [d for d in run.plan['days'] if run.batch_of(d['day']) == key]
            r = run.lessons(key, batch) or {}
            facts['lessons'] = dict(batch=key, status=r.get('status'), reason=r.get('reason'))
            if r.get('status') not in X.FINISHED:
                return ('waiting' if r.get('status') == 'waiting' else 'failed'), facts
            if _boundary(run, e, 'lessons', key, r, code_root, commit, log, facts):
                return 'failed', facts
            run.check_save()
        if key and key.startswith('discovery') and run.finished('lessons', key) and not run.finished('survivors', key):
            # stage 10 at the batch boundary (Run.lessons runs it after recording the lessons; this covers a batch whose
            # lessons finished earlier); never a gate on the day: its outcome is listed in the facts
            batch = [d for d in run.plan['days'] if run.batch_of(d['day']) == key]
            r = run.survivors(key, batch) or {}
        if key and key.startswith('discovery'):
            r = run.receipt('survivors', key) or {}
            facts['survivors'] = dict(batch=key, status=r.get('status'), reason=r.get('reason'))
            if _boundary(run, e, 'survivors', key, r, code_root, commit, log, facts):
                return 'failed', facts
            run.check_save()

    # Jev remains blind: his stage reads only the governed classroom material, never Frankie's answers (sealed first).
    if not e['classroom_arm']:
        for stage in ('classroom', 'jev', 'exchange', 'voice', 'school', 'reports'):
            r = run.guarded(stage, e) or {}
            facts[stage] = dict(status=r.get('status'), reason=r.get('reason'))
            if r.get('status') != 'skipped':
                return ('waiting' if r.get('status') == 'waiting' else 'failed'), facts
        return _close(run, e, facts)
    # F1: a Jev already finished for the day is read back, never rebuilt on a later booking (a retried finish)
    already = run.finished('jev', e['day'])
    j = (run.receipt('jev', e['day']) if already else run.guarded('jev', e)) or {}
    facts['jev'] = dict(status=j.get('status'), reason=j.get('reason'), material_sent=j.get('material_sent'),
                        dispatches=j.get('dispatches'), receipt_read_back=already or None)
    if j.get('status') not in X.FINISHED:
        return ('waiting' if j.get('status') == 'waiting' else 'failed'), facts
    if _boundary(run, e, 'jev', e['day'], j, code_root, commit, log, facts):
        return 'failed', facts
    run.check_save()
    # R-A (fresh review): Jev finishes after the class line rendered the reports; their 99-layer join now has a late
    # piece (Jev's lists, a candidates update). A revision under the same number, in this same slot, no model call;
    # its outcome is listed in the facts and never gates the day's close
    try:
        stale = run.reports_stale(e)
    except Exception as error:      # noqa: BLE001 - e.g. a corrupt school chain: named in the facts, never the day's close
        stale, facts['reports_revision'] = False, dict(status='not_checked', reason='%s: %s' % (type(error).__name__, error))
    if stale:
        r = run.guarded('reports', e) or {}
        facts['reports_revision'] = dict(status=r.get('status'), reason=r.get('reason'),
                                         trigger='late pieces after Jev (reports_stale)')
    return _close(run, e, facts)


OWNER_CLASS_POLL = 15        # seconds between the owning day's reads of its class entry (performance pass, 2026-10-07)


def _close(run, e, facts):
    """The day's successor inbox closed behind its last step: finished; or waiting while a request is still
    unacknowledged (successor_dispatch.close_day returns the pending names instead of looping on the inbox: an owner
    school recovery waiting on its meeting, a child failure awaiting its named retry). The entry records waiting with
    them; the next worker start drains again. The finish thread is not held."""
    import frankie_box_successor_dispatch as S
    closed = S.close_day(run, e['day'])
    facts['successors'] = closed
    if isinstance(closed, dict) and closed.get('status') == 'waiting':
        return 'waiting', facts
    return 'finished', facts


def _child_save_verdict(run, e, cl):
    """None while the class child has not answered the save; else the verdict: {'state': 'acknowledged', 'ack': ...}
    when the class entry is saved with an acknowledgment bound to this owner's marker, booking and attempt; 'done' /
    'failed' when the class ended on its own; 'unknown' when the child is gone without one or the ack binds elsewhere."""
    state = (cl or {}).get('state')
    if cl is None:
        return dict(state='no_child_running', reason='no class entry for the day: no child to acknowledge')
    if state in ('done', 'failed'):
        return dict(state=state, reason=cl.get('reason'))
    ack = cl.get('save_ack')
    if state == 'saved' and not ack:
        return dict(state='unknown', reason='the class entry is saved without an acknowledgment on it: nothing binds it to this save')
    if state == 'saved' and ack:
        standing = marker_identity(run.owner.get('marker'))
        # the exact binding: owner (marker), attempt, booking AND its CPU set, source, and the save's generation
        bound = (ack.get('marker') == run.owner.get('marker') and ack.get('root_attempt') == run.owner.get('attempt')
                 and ack.get('booking') == getattr(run, 'slot_booking', None)
                 and ack.get('cpus') == run.owner.get('cpus')
                 and ack.get('source_owner') == getattr(run, 'source_owner', None)
                 and standing is not None and ack.get('request') == standing)
        if bound:
            return dict(state='acknowledged', ack=ack)
        return dict(state='unknown', ack=ack, reason='the class acknowledgment binds another marker/attempt/booking/CPUs/source '
                    'or an earlier save request (the standing marker\'s identity is %s)' % ((standing or {}).get('sha256') or 'none'))
    if state == 'queued':
        # not taken by the class worker yet: no child runs; the class worker will not take it while the booking is
        # retained (no live holder), so the owner's save stands on its own
        return dict(state='no_child_running', reason='the class entry is queued, not taken: no child to acknowledge')
    att = (cl.get('attempts') or [{}])[-1]
    pid = att.get('pid') if state == 'running' else None
    if pid and not Path('/proc/%d' % pid).exists():
        return dict(state='unknown', reason='the class child (pid %d) is gone without a saved acknowledgment' % pid)
    return None


def _thread_end(error, facts, holder, entry, run_obj, failure_label):
    """The one classification of a day thread's exception: exit 75 on the day's OWN standing marker is saved (with the
    class child's verdict); any other SystemExit or exception is the day's failure under the caller's label."""
    if isinstance(error, SystemExit) and error.code == 75 and run_obj is not None and run_obj.save_requested():
        _save_result(error, facts, holder, entry, run_obj)
        return
    holder['result'] = (failure_label, '%s: %s' % (type(error).__name__, error), {})


def _save_result(error, facts, holder, entry, run_obj):
    """A SystemExit(75) in the day's thread: saved when the save is this owner's (its marker stands) and, for a class-arm
    day in its class phase, the child acknowledged; unknown when the child is gone without one."""
    facts = dict(getattr(run_obj, 'save_facts', None) or facts or {})
    root = holder.get('root')
    if root is not None:
        facts.update(root_done=True, calculations=root.get('calculations'), root_status=root['status'])
    child = facts.get('child') or {}
    if child.get('state') == 'unknown':
        holder['result'] = ('unknown', 'saved without the class child\'s acknowledgment: %s' % child.get('reason'), facts)
    else:
        holder['result'] = ('saved', 'saved on its day-bound marker %s' % ((run_obj.owner or {}).get('marker') if run_obj else None),
                            facts)


def _finish_job(entry, code_root, commit, log, holder):
    """A day whose ROOT is done but whose day is not (its ROOT ran on a Pod, or before the whole-day rule): the rest
    of the day in a box slot, ahead of any new ROOT (Greg, 2026-09-30: "when 2 spots open put them back so they can
    finish")."""
    run = None
    facts = {}
    try:
        run, e = _run_for(entry, code_root, commit, log)
        run.slot_booking = holder['slot']
        ok, facts = _finish_day(run, e, code_root, commit, log)
        status = facts.get('finish') if facts.get('finish') in ('finished', 'waiting') else 'failed'
        holder['result'] = (status, None if ok else 'the day stopped (%s) at: %s' % (status, json.dumps(
            {k: (v or {}).get('reason') if isinstance(v, dict) else v for k, v in facts.items()
             if k not in ('inspection', 'finish')}, sort_keys=True)), facts)
    except (Exception, SystemExit) as error:
        _thread_end(error, facts, holder, entry, run, 'finish_failed')
    finally:
        _end_slot(holder, entry, run)


def _needs_finish(x, plans):
    """A done ROOT-line entry whose whole day (teacher, Frankie's class, Jev) has not finished in a slot yet: its ROOT
    ran on a Pod, before the whole-day rule, or its finish failed or stopped waiting (retried once per worker start)."""
    if x['state'] != 'done' or (x.get('finish') or {}).get('state') in ('finished',) + OWNER_STATES:
        return False                                # a saved/unknown finish is its owner's: ACTION=resume, never admission
    if str(x.get('where') or '').startswith('worker:'):
        return False
    if 'pod:' in str(x.get('done_by') or '') or str(x.get('where') or '').startswith('pod:'):
        return False                                # its ROOT ran on a Pod: the day finishes in its Pod (never a box slot)
    if x['run'] not in plans:
        plans[x['run']] = _plan_of(x['run'])
    return any(d['day'] == x['day'] for d in plans[x['run']].get('days') or [])


def _standing_release(entry):
    """The day's standing save marker asks for its booking to be RELEASED (request_save release_booking=True: the fleet
    classroom gate's fleet_waiting save) -> the marker body; else None. Read from the marker file (the entry the thread
    holds is its admission-time copy; the marker is create-only and bound to the owner), never inferred from text."""
    marker = (entry.get('owner') or {}).get('marker') or str(marker_of(entry['run'], entry['day']))
    try:
        body = json.loads(Path(marker).read_bytes())
    except (OSError, ValueError):
        return None
    return body if body.get('release_booking') is True else None


def _released_fields(holder):
    """The release facts of a slot that ended RELEASED on a fleet-gate save, for the entry's record; {} otherwise, so
    every other day's record is byte-identical to before."""
    if not holder.get('booking_released'):
        return {}
    return dict(booking_released=True, released_booking=holder.get('released_booking'), released_cpus=holder.get('released_cpus'),
                release_reason=holder.get('release_reason'))


def _end_slot(holder, entry, run):
    """The slot at the end of the day's thread: released on every ordinary end; RETAINED (the ledger keeps the exact CPUs
    for this owner, nobody else books them) when the day is saved or unknown -- except (session 8, B4) a day SAVED on a
    marker that asks `release_booking` (the fleet classroom gate's fleet_waiting save): its booking is RELEASED with the
    CPU set on the record, so the sibling holding the global lease can grow; its resume re-books (resume_owner)."""
    result = (holder.get('result') or ('ended',))[0]
    if result == 'saved':
        asked = _standing_release(entry)
        if asked is not None:
            import frankie_box_cores as C
            why = 'the day %s %s is saved at the fleet classroom gate (fleet_waiting): its booking is released so the lease ' \
                  'holder\'s classroom can grow; ACTION=resume re-books it (%s)' % (entry['run'], entry['day'], asked.get('release_reason'))
            cpus = (entry.get('owner') or {}).get('cpus') or (getattr(run, 'owner', None) or {}).get('cpus')
            try:
                rec = C.release(holder['slot'], why)
            except (OSError, ValueError) as error:
                holder['release_error'] = '%s: %s' % (type(error).__name__, error)
                print('slot %s of %s %s NOT released on its fleet-gate save (%s); it stays in the ledger, not retained either'
                      % (holder['slot'], entry['run'], entry['day'], holder['release_error']), flush=True)
                return
            holder.update(booking_released=True, released_booking=holder['slot'], release_reason=asked.get('release_reason'),
                          released_cpus=sorted((rec or {}).get('cpus') or cpus or []))
            return
    if result in OWNER_STATES:
        import frankie_box_cores as C
        try:
            C.retain(holder['slot'], entry['run'], entry['day'], attempt=(getattr(run, 'owner', None) or {}).get('attempt'),
                     reason='the day is %s on its owner; its CPUs stay its own until ACTION=resume' % result)
            holder['retained'] = holder['slot']
            return
        except (OSError, ValueError) as error:
            holder['retain_error'] = '%s: %s' % (type(error).__name__, error)
            print('slot %s of %s %s not retained (%s); it is NOT released either' % (holder['slot'], entry['run'], entry['day'],
                                                                                   holder['retain_error']), flush=True)
            return
    _release_slot(holder['slot'], 'the day %s %s left its slot: %s' % (entry['run'], entry['day'], result))


def _root_job(entry, code_root, commit, log, holder):
    """One day in a box slot (a thread): the orchestrator's own root step, then the rest of the day in the same slot."""
    run = None
    facts = {}
    try:
        run, e = _run_for(entry, code_root, commit, log)
        run.slot_booking = holder['slot']
        r = run.root(e)
        if r is not None and r['status'] in ('done', 'reused'):
            holder['root'] = r                         # a save after this point is a done entry with a saved finish
        if r is None:
            holder['result'] = ('queued', 'the disk floor: %s' % (run.stopped or {}).get('reason'), {})
        elif r['status'] in ('done', 'reused'):
            ok, facts = _finish_day(run, e, code_root, commit, log)
            holder['result'] = ('done', None, dict(facts, calculations=r.get('calculations'), root_status=r['status'],
                                                   finish=facts.get('finish') if facts.get('finish') in ('finished', 'waiting')
                                                   else 'failed'))
        elif r['status'] == 'waiting' and r.get('claim'):
            holder['result'] = ('claimed_elsewhere', r.get('reason'), dict(claim=r.get('claim')))
        elif r['status'] == 'waiting':
            holder['result'] = ('queued', r.get('reason'), {})
        else:
            holder['result'] = ('failed', '%s: %s' % (r['status'], r.get('reason')), dict(log=r.get('log')))
    except (Exception, SystemExit) as error:          # a refusal is the day's failure, never the worker's
        _thread_end(error, facts, holder, entry, run, 'failed')
    finally:
        _end_slot(holder, entry, run)


def _sync_root(doc, x, plans):
    """An entry this worker is not running: done when its ROOT is finished (a Pod import, another runner, an earlier
    attempt), running when an open claim holds it elsewhere or a ROOT of the day still runs on the box, queued again at
    its own place when its runner is gone. Returns the change or None."""
    import frankie_box_experiment as X
    import frankie_box_root_claims as claims
    if str(x.get('where') or '').startswith('worker:'):
        held = claims.holder(x['run'], x['day']) if claims.active() else None
        if held or claims._path(x['run'], x['day']).with_name(x['day'] + '.done.json').exists() or x['state'] == 'done':
            return None  # retained ownership survives interruption; only an explicit release requeues
        old_owner = x.get('where')
        _end_attempt(x, 'claim released', 'the remote owner has explicitly released its claim')
        x.update(state='queued', where=None, reason='claim of %s released; back at the same queue position' % old_owner)
        return 'queued'
    if x['state'] in OWNER_STATES:
        return None                                  # its owner's; reconciled only by ACTION=resume
    if x['state'] == 'done':
        # a done entry is reconciled for ONE thing only: its finish holder gone without a saved result (unknown, retained)
        finish = x.get('finish') or {}
        if finish.get('state') == 'running' and x.get('owner') and finish.get('pid') \
                and not Path('/proc/%d' % int(finish['pid'])).exists():
            x['finish'] = dict(finish, state='unknown', ended_utc=utc(),
                               reason='its holder (pid %s) is gone without a saved result; attempt %s and its CPUs are retained; '
                                      'ACTION=resume reconciles it' % (finish.get('pid'), x['owner'].get('attempt')))
            _retain_quietly(x)
            return 'unknown'
        return None
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
        if x.get('owner'):
            # an owned day whose holder is gone without a saved result: UNKNOWN, its attempt, CPUs and booking retained
            # (the ledger keeps them for the owner); only ACTION=resume brings it back, never a requeue
            _end_attempt(x, 'unknown', 'the owner process is gone without a saved result or acknowledgment')
            x.update(state='unknown', reason='its owner (pid %s, booking %s) is gone without a saved result; attempt %s and '
                                             'its CPUs are retained; ACTION=resume reconciles it' % (
                                                 x['owner'].get('holder_pid'), x['owner'].get('booking'), x['owner'].get('attempt')))
            _retain_quietly(x)
            return 'unknown'
        _end_attempt(x, 'runner gone', 'no open claim elsewhere, no finished ROOT, no ROOT of the day running here')
        x.update(state='queued', where=None, reason='its runner %s is gone: in line again at its own place' % x.get('where'))
        return 'queued'
    return None


def _jev_progress(run_name, day):
    """None when the day's retained Jev request made no progress a rebook would have to resume (R-C): its step receipt
    names a request and the helper receipt it names is absent or 'failed'. Otherwise the reason no queue rebook decision is
    carried (no Jev request retained, Jev done, or a helper receipt in another state: the owner decides, never guessed)."""
    import frankie_box_experiment as X
    try:
        step = json.loads((X.RUNS / run_name / 'days' / day / 'jev.json').read_bytes())
    except (OSError, ValueError):
        return 'no readable Jev step receipt for the day (nothing retained to rebook)'
    if not step.get('request'):
        return 'the Jev step receipt names no retained request'
    if step.get('status') in X.FINISHED:
        return 'Jev is %s (read back, never rebuilt)' % step.get('status')
    helper = step.get('receipt')
    if helper:
        try:
            status = json.loads(Path(helper).read_bytes()).get('status')
        except OSError:
            status = None
        except ValueError:
            return 'the Jev helper receipt %s is unreadable JSON: an integrity question for the owner' % helper
        if status not in (None, 'failed'):
            return 'the Jev helper receipt is %s (progress the owner decides on)' % status
    return None


def _note_release(x, holder):
    """A slot released on a fleet-gate save: the release facts on the owner binding (resume_owner reads them to re-book)
    and on the standing save record. Nothing for any other end."""
    facts = _released_fields(holder)
    if not facts:
        return
    x['owner'] = dict(x.get('owner') or {}, **facts)
    if isinstance(x.get('save_request'), dict):
        x['save_request'].update(facts)


def _release_owner(x, why, failed_finish=False):
    """A failed (never saved) day gives its owner binding up: kept as history, so the once-per-worker retry binds afresh
    (the next attempt number, any free 16 CPUs) exactly as before the contract. The booking itself was released by the
    thread's end. Never for a saved/unknown day."""
    owner = x.get('owner')
    if owner is None:
        return
    archived = _archive_marker(owner.get('marker'), 'stale')
    if archived:
        x['save_request'] = None
        x.setdefault('save_requests_stale', []).append(dict(archived=archived, why=why, at_utc=utc()))
    x.setdefault('owner_history', []).append(dict(owner, released_utc=utc(), released_why=why))
    if failed_finish:
        # R-C (fresh review): the bookings this owner held, carried to the retry's binding (_bind_owner), which turns
        # them into a queue rebook decision only when the day's retained Jev request made no progress (its helper
        # receipt failed or absent), so Run.jev_rebooked mints the .rebookN successor instead of refusing forever
        held = list(owner.get('held_bookings') or [])
        if owner.get('booking') and not any(h.get('booking') == owner['booking'] for h in held):
            held.append(dict(booking=owner['booking'], cpus=sorted(owner.get('cpus') or [])))
        x['failed_finish_bookings'] = dict(held_bookings=held, booking=owner.get('booking'), cpus=owner.get('cpus'),
                                           attempt=owner.get('attempt'), released_utc=utc(), why=why)
    x['owner'] = None


def _rebook_owner(x, why):
    """A WAITING finish keeps its owner binding (run, day, host, attempt, marker, source) and records the queue's explicit
    REBOOK decision on it (second review F1, 2026-10-07): its booking was released by the thread's end, so the once-per-
    worker retry books any free 16 CPUs (cpus/booking cleared, as resume_owner REBOOK=on does) and _bind_owner binds the
    new booking to the SAME owner. The decision names the booking/CPUs it replaces and every booking this owner held, so
    Run.jev_rebooked mints the create-only .rebookN successor of a retained Jev request (its progress resumed, never
    re-minted) instead of refusing it. A standing save marker that the waiting finish never answered is archived as
    stale, exactly as before (an earlier save never satisfies a later one). Never for a saved/unknown day."""
    owner = x.get('owner')
    if owner is None:
        return
    archived = _archive_marker(owner.get('marker'), 'stale')
    if archived:
        x['save_request'] = None
        x.setdefault('save_requests_stale', []).append(dict(archived=archived, why=why, at_utc=utc()))
    held = list(owner.get('held_bookings') or [])
    if owner.get('booking') and not any(h.get('booking') == owner['booking'] for h in held):
        held.append(dict(booking=owner['booking'], cpus=sorted(owner.get('cpus') or [])))
    decision = dict(by='queue', reason=why, at_utc=utc(), previous_booking=owner.get('booking'),
                    previous_cpus=owner.get('cpus'), held_bookings=held,
                    rule='the queue\'s own retry of a waiting finish on a new booking of the same owner binding')
    x.setdefault('owner_rebooks', []).append(decision)
    x['owner'] = dict(owner, cpus=None, booking=None, rebooked=decision)


def _archive_marker(marker, label):
    """The day's save marker and its class acknowledgment moved aside as <name>.<label>-<epoch> (never deleted)."""
    if not marker:
        return []
    stamp = int(time.time())
    archived = []
    for path in (Path(marker), Path(str(marker) + '.class-ack.json'), Path(str(marker) + '.clean.json')):   # session 6 review H
        if path.exists():
            target = path.with_name('%s.%s-%d' % (path.name, label, stamp))
            os.rename(path, target)
            archived.append(str(target))
    return archived


def _retain_quietly(x):
    """The ledger told that the owner's booking is retained (a dead-holder booking would be reaped otherwise)."""
    import frankie_box_cores as C
    booking = (x.get('owner') or {}).get('booking')
    if not booking:
        return
    try:
        C.retain(booking, x['run'], x['day'], attempt=x['owner'].get('attempt'), reason='the owner is gone: unknown')
    except (OSError, ValueError) as error:
        x['owner']['retain_error'] = '%s: %s' % (type(error).__name__, error)


def root_worker(code_root, commit, max_seconds, poll_seconds, log=print, wait_lock=False, scope=None):
    """The one ROOT worker: box slots filled from the front of the ROOT line in arrival order; Pod claims followed. It
    never starts a ROOT after its bound or a stop signal, and waits for the ROOTs it started (their receipts are theirs).
    Each box-slot day runs its whole day in the slot (ROOT, its teacher, the class line); days whose ROOT is done but
    whose day is not take free slots first. Everything it reconciles, admits or receipts is inside its scope."""
    scope = parse_scope(scope)
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
                   poll_seconds=poll_seconds, started_utc=utc(), scope=scope['text'])
    while True:
        if time.monotonic() >= deadline:
            stop.setdefault('reason', 'the time bound (%d s)' % max_seconds)
        finished = [seq for seq, job in running.items() if not job['thread'].is_alive()]
        after, owner_waiting = [], []
        with locked():
            doc = load('root')
            for seq in finished:
                job = running.pop(seq)
                y = find(doc, seq)
                result, reason, facts = job['holder'].get('result') or ('failed', 'the slot ended without a result', {})
                if job.get('kind') == 'finish':
                    y['finish'] = dict(y.get('finish') or {}, state=result if result in OWNER_STATES + ('finished', 'waiting')
                                       else 'failed', reason=reason, ended_utc=utc(), facts=facts,
                                       retained_booking=job['holder'].get('retained'), child=facts.get('child'),
                                       inspection=facts.get('inspection'), **_released_fields(job['holder']))
                    _note_release(y, job['holder'])
                    if y['finish']['state'] == 'failed':
                        _release_owner(y, 'finish failed: the next admission books any free slot; the owner binding is history',
                                       failed_finish=True)
                    elif y['finish']['state'] == 'waiting':
                        # F1: a wait stays a wait; the retry binds a new booking to the SAME owner with a recorded
                        # rebook decision, so a done or pending Jev is reused/resumed, never refused
                        _rebook_owner(y, 'finish waiting: the retry books any free 16 CPUs for the same owner binding')
                    event('root', 'finish_end', seq=seq, day=y['day'], run=y['run'], result=result, reason=reason, facts=facts)
                    log('FINISH seq %d %s (%s): %s%s' % (seq, y['day'], y['run'], result, (': %s' % reason) if reason else ''))
                    continue
                _end_attempt(y, result, reason)
                y['attempts'][-1].update(facts)
                if result in OWNER_STATES and facts.get('root_done'):
                    # the ROOT finished in this slot before the save: the entry is DONE with a saved/unknown finish, so a
                    # resume takes the finish path and never rediscovers its own ROOT as another runner's
                    y.update(state='done', reason=None, where='box-slot', calculations=facts.get('calculations'),
                             done_seq=doc['next_done_seq'], done_at=time.time(), done_utc=utc(),
                             finish=dict(state=result, reason=reason, ended_utc=utc(), facts=facts,
                                         retained_booking=job['holder'].get('retained'), child=facts.get('child'),
                                         **_released_fields(job['holder'])))
                    _note_release(y, job['holder'])
                    doc['next_done_seq'] += 1
                    event('root', 'slot_' + result, seq=seq, day=y['day'], run=y['run'], reason=reason, owner=y.get('owner'),
                          child=facts.get('child'), root_done=True)
                    log('ROOT seq %d %s (%s): ROOT done, then %s: %s (attempt %s, CPUs %s retained)' % (
                        seq, y['day'], y['run'], result, reason, (y.get('owner') or {}).get('attempt'),
                        (y.get('owner') or {}).get('cpus')))
                    continue
                if result in OWNER_STATES:
                    y.update(state=result, reason=reason, retained_booking=job['holder'].get('retained'),
                             retain_error=job['holder'].get('retain_error'), child=facts.get('child'),
                             **_released_fields(job['holder']))
                    _note_release(y, job['holder'])
                    event('root', 'slot_' + result, seq=seq, day=y['day'], run=y['run'], reason=reason, owner=y.get('owner'),
                          child=facts.get('child'))
                    log('ROOT seq %d %s (%s): %s: %s (attempt %s, CPUs %s retained)' % (
                        seq, y['day'], y['run'], result, reason, (y.get('owner') or {}).get('attempt'),
                        (y.get('owner') or {}).get('cpus')))
                    continue
                if result == 'done':
                    y.update(state='done', reason=None, where='box-slot', calculations=facts.get('calculations'),
                             class_line=facts.get('class_line'), done_seq=doc['next_done_seq'], done_at=time.time(),
                             done_utc=utc(), finish=dict(state=facts.get('finish') if facts.get('finish') in ('finished', 'waiting')
                                                         else 'failed',
                                                         reason=None if facts.get('finish') == 'finished' else
                                                         {k: (v or {}).get('reason') if isinstance(v, dict) else v
                                                          for k, v in facts.items()
                                                          if k not in ('inspection', 'finish', 'calculations', 'root_status')},
                                                         facts={k: facts.get(k) for k in ('teacher', 'class_line')},
                                                         inspection=facts.get('inspection'), ended_utc=utc()))
                    doc['next_done_seq'] += 1
                    if y['finish']['state'] == 'waiting':
                        # F1, the same rule on the ROOT-and-finish-in-one-slot route: the retry rebinds the same owner
                        _rebook_owner(y, 'finish waiting: the retry books any free 16 CPUs for the same owner binding')
                    elif y['finish']['state'] == 'failed':
                        # the same rule as the finish-only route above (2026-10-07 night, the gap ccode_step8 named): a
                        # failed finish gives its owner binding up, kept as history. Kept, it would pin the retry to the
                        # exact CPUs of a booking the thread's end already released (_book_slot books owner['cpus']), so
                        # the retry waits on whichever day took them. The retry binds afresh: root_of names the SAME
                        # completed ROOT attempt, any free 16 CPUs. A done Jev is read back (Run.jev_done_receipt); a
                        # failed or pending Jev bound to the released booking needs ACTION=resume REBOOK=on, as on the
                        # finish-only route (a failure is not a wait).
                        _release_owner(y, 'finish failed after the ROOT in the same slot: the next admission books any '
                                          'free slot; the owner binding is history', failed_finish=True)
                elif result == 'claimed_elsewhere':
                    y.update(state='running', where=(facts.get('claim') or {}).get('where'), reason=reason)
                    _release_owner(y, 'claimed elsewhere: this box holds nothing of the day')
                elif result == 'queued':
                    y.update(state='queued', where=None, reason='back in line at its own place: %s' % reason)
                    _release_owner(y, 'back in line before any work: the next admission binds afresh on free CPUs')
                else:
                    y.update(state='failed', where=None, reason=reason)
                    _release_owner(y, 'failed: the attempt is kept as evidence; a retry mints the next attempt on free CPUs')
                event('root', 'slot_end', seq=seq, day=y['day'], run=y['run'], result=result, reason=reason, facts=facts)
                log('ROOT seq %d %s (%s): %s%s' % (seq, y['day'], y['run'], result, (': %s' % reason) if reason else ''))
            for x in ordered(doc):
                if not in_scope(x, scope):
                    continue                                # outside the authorization: left exactly as it is
                if (x['seq'] not in running and not str(x.get('where') or '').startswith('worker:') and
                        (x['state'] != 'done' or _needs_finish(x, plans) or x.get('needs_receipt'))):
                    why = _source_wait(x, code_root, commit)
                    if why:
                        x['reason'] = why
                        owner_waiting.append(x)
                        continue                            # do not reconcile another source's retained attempt
                if (x['state'] != 'done' or (x.get('finish') or {}).get('state') == 'running') and x['seq'] not in running:
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
            out_of_scope_ahead = None
            for x in ordered(doc):
                if stop or x['seq'] in running or not _needs_finish(x, plans):
                    continue
                if not in_scope(x, scope):
                    continue                                # its own scope's worker finishes it
                why = _source_wait(x, code_root, commit)
                if why:
                    x['reason'] = source = why
                    continue                                # no booking, attempt mutation or failed-day retry
                if (x.get('finish') or {}).get('state') in ('failed', 'waiting'):
                    if x['seq'] in retried:
                        continue                            # a failed or waiting finish is retried once per worker start
                    retried.add(x['seq'])
                slot, cpus, why = _book_slot(x, 'finish', commit)
                if slot is None:
                    source = why
                    break                                   # no free slot: the days behind wait
                holder = dict(slot=slot)
                _bind_source(x, code_root, commit)
                try:
                    _bind_owner(x, slot, cpus, code_root, commit)   # the owner binding is durable BEFORE the thread starts
                except (Exception, SystemExit) as error:            # a refusal of the day, never the worker's end
                    _release_slot(slot, 'the owner binding of %s %s was refused: %s' % (x['run'], x['day'], error))
                    x['finish'] = dict(x.get('finish') or {}, state='failed', reason='owner binding refused: %s' % error)
                    _release_owner(x, 'owner binding refused on the finish path')
                    event('root', 'finish_refused', seq=x['seq'], day=x['day'], run=x['run'], reason=str(error))
                    continue
                x['finish'] = dict(state='running', started_utc=utc(), pid=os.getpid(), commit=commit, slot_booking=slot)
                save('root', doc)                            # retain source before the child thread can do work
                t = threading.Thread(target=_finish_job, args=(dict(x), code_root, commit, log, holder), daemon=True)
                running[x['seq']] = dict(thread=t, holder=holder, kind='finish')
                t.start()
                event('root', 'finish_take', seq=x['seq'], day=x['day'], run=x['run'], where='box-slot', slot_booking=slot)
            for x in ordered(doc):
                if owner_waiting:
                    break                                   # retained owner recovery precedes new day admission
                if x['state'] in ('done', 'running') + OWNER_STATES:
                    continue                                # a saved/unknown day is its owner's (ACTION=resume), not admitted
                if not in_scope(x, scope):
                    # an out-of-scope predecessor that has not started: FIFO makes the eligible days behind it wait;
                    # this worker never starts it (a predecessor cannot widen the authorization)
                    out_of_scope_ahead = x
                    source = 'seq %d day %s run %s is outside this worker\'s scope %s and has not started: the days behind ' \
                             'it wait (FIFO); a kick with its scope takes it' % (x['seq'], x['day'], x['run'], scope['text'])
                    break
                why = _source_wait(x, code_root, commit)
                if why:
                    x['reason'] = source = why
                    break                                   # FIFO: a retained-source refusal never admits its successor
                if x['state'] == 'failed':
                    if x['seq'] in retried:
                        blocked = x
                        break                               # the line stops at a failed entry (never skipped)
                    retried.add(x['seq'])                   # retried once per worker start
                if stop:
                    break
                slot, cpus, why = _book_slot(x, 'root', commit)
                if slot is None:
                    source = why
                    break                                   # no free slot: everything behind the front waits
                holder = dict(slot=slot)
                _bind_source(x, code_root, commit)
                try:
                    owner = _bind_owner(x, slot, cpus, code_root, commit)   # durable BEFORE the thread: attempt, CPUs, marker
                except (Exception, SystemExit) as error:                    # a refusal of the day, never the worker's end
                    _release_slot(slot, 'the owner binding of %s %s was refused: %s' % (x['run'], x['day'], error))
                    x.update(state='failed', where=None, reason='owner binding refused: %s' % error)
                    event('root', 'take_refused', seq=x['seq'], day=x['day'], run=x['run'], reason=str(error))
                    continue
                x.setdefault('attempts', []).append(dict(where='box-slot', pid=os.getpid(), commit=commit,
                                                         started=time.time(), started_utc=utc(), slot_booking=slot,
                                                         attempt=owner['attempt'], cpus=owner['cpus']))
                x.update(state='running', where='box-slot', reason='its whole day in the held box slot %s' % slot)
                save('root', doc)                            # intent is durable before scientific work starts
                t = threading.Thread(target=_root_job, args=(dict(x), code_root, commit, log, holder), daemon=True)
                running[x['seq']] = dict(thread=t, holder=holder)
                t.start()
                event('root', 'take', seq=x['seq'], day=x['day'], run=x['run'], where='box-slot', slot_booking=slot)
            save('root', doc)
            mine = [x for x in doc['entries'] if in_scope(x, scope)]
            pending = [x for x in mine if x['state'] != 'done' or (x.get('finish') or {}).get('state') in OWNER_STATES or
                       ((x.get('finish') or {}).get('state') not in ('finished', 'failed') and _needs_finish(x, plans))]
            owned = [x for x in pending if x['state'] in OWNER_STATES or (x.get('finish') or {}).get('state') in OWNER_STATES]
            n_done = len(mine) - len(pending)
            end = None
            if not running and owner_waiting and not after:
                blocked = owner_waiting[0]
                end = ('waiting_owner', 5)
            elif not running and pending and not after and len(owned) == len(pending):
                blocked = owned[0]                           # every pending day is saved/unknown: its owner's ACTION=resume
                end = ('waiting_owner', 5)
            elif not running and not pending and not after:
                end = ('idle', 0)                            # nothing of this scope left; other scopes' days are untouched
            elif not running and not after and out_of_scope_ahead is not None and pending and \
                    all(x['state'] not in ('running',) for x in pending):
                blocked = out_of_scope_ahead
                end = ('waiting_out_of_scope', 5)
            elif not running and not after and blocked is not None and all(x['state'] != 'running' for x in pending):
                end = ('stopped_at_failed', 3)
            elif not running and stop and not after:
                end = ('saved', 5)
            if end:
                about = None if blocked is None else dict(seq=blocked['seq'], day=blocked['day'], run=blocked['run'],
                                                          reason=blocked.get('reason'))
                _worker_status('root', state=end[0], commit=commit, scope=scope['text'],
                               reason=blocked.get('reason') if end[0] == 'waiting_owner' else source if end[0] == 'waiting_out_of_scope'
                               else stop.get('reason'), front=about, pending=len(pending))
                event('root', 'worker_end', state=end[0], reason=stop.get('reason'), front=about, pending=len(pending),
                      scope=scope['text'])
                probe.update('root:' + end[0], n_done, len(mine) or None,
                             state='waiting' if end[0] in ('waiting_owner', 'waiting_out_of_scope') else 'complete' if end[1] == 0 else 'failed')
                fcntl.flock(lock, fcntl.LOCK_UN)            # released under the queue lock: an enqueue now gets a new kick
                lock.close()
                code = end[1]
                break
        for x in after:                                     # a ROOT finished elsewhere: its step receipt, then the class line
            if not in_scope(x, scope):
                continue
            why = _source_wait(x, code_root, commit)
            if why:
                with locked():
                    doc = load('root')
                    y = find(doc, x['seq'])
                    y.update(reason=why, needs_receipt=True)
                    save('root', doc)
                    event('root', 'receipt_waiting_owner', seq=x['seq'], day=x['day'], run=x['run'], reason=why)
                continue
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
                       pending=len(pending), scope=scope['text'])
        probe.update('root:running %d' % len(running), n_done, len(mine) or None, in_flight=len(running))
        time.sleep(poll_seconds)
    return code


# ------------------------------------------------------------------------------------- save / status / resume (the owner)

def request_save(run, day, by, release_booking=False, release_reason=None):
    """The day-bound save: the owner's marker written create-only. Allowed while the day's owner runs (the ROOT line entry
    running, or done with its finish running). The owner stops at its next boundary; a class-arm day in its class phase
    waits for the class child's acknowledgment first. Returns what stands; never kills, clears or completes anything.
    release_booking (session 8, B4): True ONLY for the fleet classroom gate's fleet_waiting save: the marker carries
    `release_booking: true` (+ release_reason) and _end_slot RELEASES the day's CPU booking instead of retaining it, so
    the sibling day holding the global classroom lease can grow to the whole box; resume_owner re-books it. False (the
    default: the hold, the stage handoff's ordinary save, an operator save) writes the marker exactly as before."""
    with locked():
        doc = load('root')
        x = next((y for y in doc['entries'] if y['run'] == run and y['day'] == day), None)
        if x is None:
            raise SystemExit('%s %s is not in the ROOT line' % (run, day))
        owner = x.get('owner')
        if owner is None:
            raise SystemExit('%s %s has no owner binding (it never started under the owner contract); nothing to save' % (run, day))
        active = x['state'] == 'running' or (x['state'] == 'done' and (x.get('finish') or {}).get('state') == 'running')
        if not active:
            raise SystemExit('%s %s is %s (finish %s): a save applies to a running owner only' % (
                run, day, x['state'], (x.get('finish') or {}).get('state')))
        import frankie_box_cores as C
        marker = Path(owner['marker'])
        body = dict(schema='FRANKIE_QUEUE_SAVE_REQUEST_V1', run=run, day=day, attempt=owner['attempt'], booking=owner.get('booking'),
                    cpus=owner.get('cpus'), requested_at=time.time(), requested_utc=utc(), by=by)
        if release_booking:
            body.update(release_booking=True, release_reason=release_reason or 'fleet classroom gate: the day waits for the '
                        'global classroom lease; its CPUs go to the holder\'s classroom')
        try:
            C.write_json(marker, body, exclusive=True)
        except FileExistsError:
            raise SystemExit('a save request stands already: %s' % marker)
        x['save_request'] = dict(body, identity=marker_identity(marker))
        save('root', doc)
        event('root', 'save_requested', seq=x['seq'], day=day, run=run, marker=str(marker), by=by,
              **(dict(release_booking=True) if release_booking else {}))
        return dict(requested=body, marker=str(marker), entry_state=x['state'],
                    note='the owner stops at its next boundary; a class in progress acknowledges first; ACTION=status shows it'
                         + ('; its booking is RELEASED at that boundary (fleet gate save); ACTION=resume re-books it'
                            if release_booking else ''))


def owner_status(run, day):
    """The owner, its save request and acknowledgments, the ROOT-line and class-line entries, the ledger booking (live,
    retained or gone), the marker and ack files. Read-only."""
    import frankie_box_cores as C
    root = entry_of('root', run, day)
    cls = entry_of('class', run, day)
    owner = (root or {}).get('owner')
    booking = None
    if owner and owner.get('booking'):
        path = C.LEDGER / (owner['booking'] + '.json')
        if path.is_file():
            b = json.loads(path.read_bytes())
            booking = dict(booking=owner['booking'], cpus=b.get('cpu_list'), alive=any(C.alive(p) for p in b.get('pids') or []),
                           retained=b.get('retained'))
        else:
            released = C.RELEASED / (owner['booking'] + '.json')
            booking = dict(booking=owner['booking'], released=json.loads(released.read_bytes()).get('release_reason')
                           if released.is_file() else 'no ledger record')
    marker = Path(owner['marker']) if owner else None
    ack_path = Path(str(marker) + '.class-ack.json') if marker else None
    clean_note = Path(str(marker) + '.clean.json') if marker else None     # session 6: the clean unit's outcome, if any
    return dict(schema='FRANKIE_QUEUE_OWNER_STATUS_V1', run=run, day=day, owner=owner,
                clean=json.loads(clean_note.read_bytes()) if clean_note and clean_note.is_file() else None,
                root_entry={k: (root or {}).get(k) for k in ('seq', 'state', 'reason', 'finish', 'save_request', 'child',
                                                           'retained_booking', 'retain_error', 'attempts')},
                class_entry={k: (cls or {}).get(k) for k in ('seq', 'state', 'reason', 'school_day', 'slot_booking', 'save_ack',
                                                           'attempts')} if cls else None,
                booking=booking, marker=dict(path=str(marker), standing=marker.is_file(), identity=marker_identity(marker)) if marker else None,
                class_ack=json.loads(ack_path.read_bytes()) if ack_path and ack_path.is_file() else None,
                worker=worker_state('root')[0],
                verdict=('saved' if (root or {}).get('state') == 'saved' or ((root or {}).get('finish') or {}).get('state') == 'saved'
                         else 'unknown' if (root or {}).get('state') == 'unknown' or ((root or {}).get('finish') or {}).get('state') == 'unknown'
                         else 'save pending acknowledgment' if (root or {}).get('save_request') else (root or {}).get('state')))


def retire_run(run, by, reason):
    """ACTION=retire RUN=: a dead run's line entries leave both lines' active lists and are kept, whole, under the line's
    `retired` list with the record (who, when, the reason, their state then); nothing is deleted. Its duplicate-data
    claim on a day then no longer blocks a new run of the same day. Refused (nothing changed) while any of the run's
    entries is running or unknown and that line's worker is alive. Its retained bookings, ROOT directories, receipts and
    brain entries are untouched (listed by their own owners)."""
    if not reason:
        raise SystemExit('ACTION=retire needs REASON (recorded on every retired entry)')
    out = {}
    with locked():
        docs = {line: load(line) for line in LINES}
        for line, doc in docs.items():
            live = [x for x in doc['entries'] if x['run'] == run and _entry_running(x)]
            if live and worker_state(line)[1]:
                raise SystemExit('%s: %s entr%s of run %s running/unknown while the %s worker is alive (%s); nothing retired' % (
                    line, len(live), 'y' if len(live) == 1 else 'ies', run, line,
                    ', '.join('seq %d %s %s' % (x['seq'], x['day'], x['state']) for x in live)))
        for line, doc in docs.items():
            mine = [x for x in doc['entries'] if x['run'] == run]
            if not mine:
                out[line] = []
                continue
            record = dict(by=by, reason=reason, at_utc=utc(), at=time.time(), pid=os.getpid(), host=socket.gethostname())
            for x in mine:
                doc.setdefault('retired', []).append(dict(x, retired=dict(record, state_then=x['state'],
                                                                         finish_then=(x.get('finish') or {}).get('state'))))
            doc['entries'] = [x for x in doc['entries'] if x['run'] != run]
            save(line, doc)
            for x in mine:
                event(line, 'retired', seq=x['seq'], run=run, day=x['day'], state=x['state'], by=by, reason=reason)
            out[line] = [dict(seq=x['seq'], day=x['day'], state=x['state']) for x in mine]
    # session 6 review finding 6 (Patch F): the retired run's bind-mount fstab lines (frankie-clean run=<run>) are umounted
    # and removed; the archive copies stay where they are
    try:
        import frankie_box_root_move as M
        fstab_bind_lines = M.remove_fstab_lines(run)
    except Exception as error:  # noqa: BLE001 - named, never the retire's outcome
        fstab_bind_lines = dict(error='%s: %s' % (type(error).__name__, error))
    return dict(schema='FRANKIE_QUEUE_RETIRE_V1', run=run, retired=out, by=by, reason=reason, fstab_bind_lines=fstab_bind_lines,
                note='entries kept under each line\'s retired list; bookings, ROOT directories, receipts and brain entries '
                     'untouched')


def resume_owner(run, day, by, rebook=False):
    """The explicit resume of a saved/unknown owned day: its marker archived beside its acknowledgment, the ROOT-line entry
    (and its class entry) back to queued WITH the same owner binding (attempt, CPUs, booking, marker), so the next
    admission books exactly the retained CPUs and the Run resumes the same attempt. Nothing is reconciled by guessing: an
    unknown day is resumed as the same attempt (its continuation state decides what it reuses)."""
    with locked():
        doc = load('root')
        x = next((y for y in doc['entries'] if y['run'] == run and y['day'] == day), None)
        if x is None:
            raise SystemExit('%s %s is not in the ROOT line' % (run, day))
        owner = x.get('owner')
        if owner is None:
            raise SystemExit('%s %s has no owner binding; nothing to resume' % (run, day))
        finish = x.get('finish') or {}
        import frankie_box_cores as C
        ledger = C.LEDGER / ('%s.json' % owner.get('booking'))
        retained = json.loads(ledger.read_bytes()).get('retained') if ledger.is_file() else None
        if owner.get('booking_released') and retained is None:
            # session 8 (B4): the day was saved at the fleet classroom gate and its booking RELEASED (the record says so,
            # explicitly). Re-book NOW through the ledger under its one lock -- the resolver names a lane (whole cores
            # first) and the same lane is booked and retained for this owner -- or refuse loudly with the reason; the
            # next admission then books EXACTLY the new set. The REBOOK flag is accepted and not required: the
            # release on the save is the recorded decision.
            size = int(_plan_of(run).get('day_cpus') or len(owner.get('released_cpus') or []) or C.DAY_RUN_CPUS)
            b, outcome = C.rebook_for_owner(run, day, owner['attempt'], size, 'day-slot-resume', owner.get('commit'),
                                            reason='resumed by %s after its fleet-gate release (booking %s, CPUs %s)' % (
                                                by, owner.get('released_booking'), owner.get('released_cpus')))
            if b is None:
                raise SystemExit('%s %s: its booking %s (CPUs %s) was released at the fleet classroom gate and no %d-CPU lane '
                                 'is free to re-book now: %s; the day stays %s (resume again when a lane frees)' % (
                                     run, day, owner.get('released_booking'), owner.get('released_cpus'), size,
                                     outcome.get('reason'), x['state']))
            decision = dict(by=by, at_utc=utc(), previous_cpus=owner.get('released_cpus'), previous_booking=owner.get('released_booking'),
                            booking=b['booking'], cpus=sorted(b['cpus']), size=size, resolver=outcome.get('resolver'),
                            fallback=outcome.get('fallback'), rule='re-booked at resume after a fleet-gate release (B4)')
            x['owner'] = owner = dict(owner, cpus=sorted(b['cpus']), booking=b['booking'], rebooked=decision, booking_released=False,
                                      released_history=list(owner.get('released_history') or []) + [dict(
                                          booking=owner.get('released_booking'), cpus=owner.get('released_cpus'),
                                          reason=owner.get('release_reason'), rebooked_to=b['booking'])])
            x.setdefault('owner_rebooks', []).append(decision)
            retained = b.get('retained')
        if retained is None and owner.get('cpus') and not rebook:
            released = C.RELEASED / ('%s.json' % owner.get('booking'))
            raise SystemExit('the retained booking %s of %s %s is not in the ledger any more (%s): the exact CPU set cannot be '
                             'reused; an explicit owner decision is required: REBOOK=on resumes the same attempt %s on any '
                             'free 16 CPUs' % (owner.get('booking'), run, day,
                                                json.loads(released.read_bytes()).get('release_reason') if released.is_file()
                                                else 'no ledger record', owner['attempt']))
        if rebook and retained is None:
            x['owner'] = owner = dict(owner, cpus=None, booking=None,
                                      rebooked=dict(by=by, at_utc=utc(), previous_cpus=owner.get('cpus'),
                                                    previous_booking=owner.get('booking')))
        if x['state'] in OWNER_STATES:
            x.update(state='queued', where=None, reason='resumed by %s: back in line at its own place with its owner binding '
                                                         '(attempt %s, CPUs %s)' % (by, owner['attempt'], owner.get('cpus') or 'any free 16'))
            phase = 'root'
        elif x['state'] == 'done' and finish.get('state') in OWNER_STATES:
            x['finish'] = dict(finish, state='resume', resumed_by=by, resumed_utc=utc())
            phase = 'finish'
        else:
            raise SystemExit('%s %s is %s (finish %s): only a saved/unknown day is resumed' % (run, day, x['state'], finish.get('state')))
        archived = _archive_marker(owner['marker'], 'resumed')
        x['save_request'] = None
        x.setdefault('resumes', []).append(dict(at=time.time(), at_utc=utc(), by=by, phase=phase, archived=archived))
        save('root', doc)
        event('root', 'resume', seq=x['seq'], day=day, run=run, by=by, phase=phase, archived=archived, owner=owner)
        cdoc = load('class')
        c = next((y for y in cdoc['entries'] if y['run'] == run and y['day'] == day), None)
        if c is not None and c['state'] in OWNER_STATES:
            c.update(state='queued', reason='resumed by %s with its owner binding; same school day %s, same PREVIOUS' % (
                by, c.get('school_day')))
            save('class', cdoc)
            event('class', 'resume', seq=c['seq'], day=day, run=run, by=by)
        return dict(resumed=dict(run=run, day=day, phase=phase, owner=owner, archived=archived),
                    note='the next ROOT-line admission books exactly the retained CPUs and resumes attempt %s; kick the '
                         'root worker with this run/day in scope' % owner['attempt'])


# ------------------------------------------------------------------------------------------------------ main

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--action', required=True, choices=('show', 'enqueue', 'worker', 'kick', 'handover', 'save', 'status', 'resume',
                                                      'retire'))
    p.add_argument('--reason', help='retire: the recorded reason')
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
    p.add_argument('--scope', help='worker/kick/handover: the authorized RUN:YYYYMMDD,... this worker may admit (required)')
    p.add_argument('--rebook', choices=('on', 'off'), default='off',
                   help='resume: the retained booking is gone (released): resume the same attempt on any free 16 CPUs')
    p.add_argument('--release-booking', choices=('on', 'off'), default='off',
                   help='save: release the day\'s CPU booking at the save boundary (the fleet classroom gate\'s fleet_waiting '
                        'save ONLY); off (default) retains it exactly as before')
    p.add_argument('--release-reason', help='save --release-booking on: the recorded reason')
    a = p.parse_args()
    if a.action == 'show':
        if a.events != 'all' and not a.events.isdigit():
            raise SystemExit('--events: a number or all')
        print(json.dumps(show(a.events), indent=1, sort_keys=True, default=str))
        return 0
    if a.action == 'retire':
        import re
        if not (a.run and re.fullmatch('[A-Za-z0-9_-]{1,64}', a.run)):
            raise SystemExit('--run [A-Za-z0-9_-] required')
        sys.path.insert(0, str(HERE))
        print(json.dumps(retire_run(a.run, 'dispatch retire', a.reason), indent=1, sort_keys=True, default=str))
        return 0
    if a.action in ('save', 'status', 'resume'):
        import re
        if not (a.run and re.fullmatch('[A-Za-z0-9_-]{1,64}', a.run) and a.day and re.fullmatch('[0-9]{8}', a.day)):
            raise SystemExit('--run [A-Za-z0-9_-] and --day YYYYMMDD required')
        sys.path.insert(0, str(HERE))
        by = 'dispatch %s' % a.action
        out = (request_save(a.run, a.day, by, release_booking=a.release_booking == 'on', release_reason=a.release_reason)
               if a.action == 'save' else owner_status(a.run, a.day) if a.action == 'status'
               else resume_owner(a.run, a.day, by, rebook=a.rebook == 'on'))
        print(json.dumps(out, indent=1, sort_keys=True, default=str))
        return 0
    if not (a.line and a.code_root and a.commit):
        raise SystemExit('--line, --code-root and --commit required')
    if a.max_seconds < 60 or a.poll_seconds < 5 or a.poll_seconds > 600:
        raise SystemExit('--max-seconds >= 60 and --poll-seconds 5..600 required')
    sys.path.insert(0, str(HERE))
    if a.action == 'worker':
        try:
            if a.line == 'class':
                code = class_worker(a.code_root, a.commit, a.max_seconds, a.poll_seconds, log=lambda t: print(t, flush=True),
                                    scope=a.scope)
            else:
                code = root_worker(a.code_root, a.commit, a.max_seconds, a.poll_seconds, log=lambda t: print(t, flush=True),
                                   wait_lock=a.wait_lock, scope=a.scope)
        finally:
            # the box's KeepRunning tag (Greg, 2026-10-07: "keep running only when in use"): a line worker's end is the
            # last work of a run on this box; cleared to false ONLY when no orchestrator start, other line worker or CPU
            # controller is alive here (frankie_box_experiment.box_in_use names what is; then the tag is kept, recorded);
            # every exit path (bound, idle, error) passes here; recorded in <run>/keep-running.json, never silent
            try:
                import frankie_box_experiment as X
                run_name = (a.scope or '').split(':', 1)[0] or 'queue'
                X.keep_running(run_name, False, '%s line worker ended (scope %s)' % (a.line, a.scope or 'none'),
                               'frankie_box_frankie_queue.py worker', log=lambda t: print(t, flush=True))
            except Exception as error:  # noqa: BLE001 - a cost guard, never the worker's outcome; named
                print('keep-running: not recorded (%s: %s)' % (type(error).__name__, error), flush=True)
        print(json.dumps(show(20)['lines'][a.line], indent=1, sort_keys=True, default=str))
        return code
    if a.action == 'kick':
        print(json.dumps(kick(a.line, a.code_root, a.commit, a.max_seconds, a.poll_seconds, by='dispatch', scope=a.scope),
                         sort_keys=True))
        return 0
    if a.action == 'handover':
        print(json.dumps(handover(a.line, a.code_root, a.commit, a.max_seconds, a.poll_seconds, scope=a.scope),
                         sort_keys=True, default=str))
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
                              by='dispatch enqueue', scope=run.scope_text()), sort_keys=True))
    return 0 if (r or {}).get('status') in ('queued', 'done', 'reused') else 3


if __name__ == '__main__':
    sys.exit(main())
