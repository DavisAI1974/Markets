"""The per-box CPU BOOKING LEDGER (Greg, 2026-09-29: "Correct 16 and no double booking"; "We don't double book cores or
workers"; "we don't schedule remaining day runs on 9 cores. They all get the same 16 and workers so we wait until 16 are
available").

THE BUG IT PREVENTS. On main (32 CPUs) an inline-verify ingest set to WORKERS=7 ran 14 workers + its parent (the encode
pool and the conformance-reader pool at once). A day run (ROOT, DATA_WORKERS=15) was started believing 16 CPUs were free;
the reader's worker_budget pins each worker to one CPU from cpus[1:] of the PROCESS'S OWN affinity, so ROOT's 15 workers
landed on CPUs 1-15, the same CPUs the ingest workers held, each at ~50%.

THE LEDGER. /opt/frankie-box/cpu-bookings/<booking id>.json, one JSON per live booking: booking id, job kind, day, run,
stage, cpus, parent cpu, pids (each with its /proc start time, so a reused pid is never taken for the job), started,
dispatch commit, the sizing rule. A released booking moves to released/<id>.json with its release receipt (never deleted);
a job that could not book writes waiting/<...>.json. Every write happens under flock on .lock, so two jobs booking at once
never take the same CPU.

SIZES (hard):
  day-run  every step of a day run the orchestrator runs (root, teacher, classroom, data, search, lessons, exchange, voice,
           school, reports, jev, survivors) books EXACTLY 16 CPUs, never fewer (or runs inside its day's held 16 or 32,
           Jev and the meeting (voice) too, like every other stage, on the whole held lane: Greg, 2026-10-07 night "day 1
           gets ALL 32 CPUs for every step"; the meeting keeps its STAGE CLAIM below, now of the whole lane). With fewer
           than 16 free it does NOT start: it records
           'waiting: N free of 16 needed' and exits 75 (a later dispatch retries). Its workers = the booked 16 less the
           parent = 15.
  ingest | canary | conform  8 CPUs per day process by default, or --size 16 / 24 / 32 (Greg, 2026-10-07 night: one day
           may take the whole box, or days side by side fill it). THE RULE (stated in every receipt): a day process runs
           ONE pool at a time (the encode pool ends at the seal, before the conformance reader starts; the parallel
           writer's replay/encode pool closes before its reader), so it needs WORKERS + 1 CPUs (it was WORKERS x 2 + 1
           for an inline verify while the idle encode pool stayed alive). A demand above the size is REFUSED with that
           reason (never booked bigger, never squeezed onto fewer). The largest WORKERS that fit: size - 1.
  Never more than nproc in total: every booking comes out of the free set.

FREE = the online CPUs, less the CPUs of live bookings, less the CPUs actually in use by any running Frankie process tree
that is NOT in the ledger: every python process whose executable, command line or working directory is under
/opt/frankie-box, and every descendant of one. Per thread (read from /proc twice, WINDOW seconds apart): a thread pinned
to fewer than all online CPUs holds every CPU of its affinity; an unpinned thread holds the CPU it last ran on when it
used at least 5% of a CPU in the window. A CPU in either set is never booked.

CPU 0 is the host / ordered-consumer CPU. A job's PARENT CPU is the lowest CPU of its booking (worker_budget reserves
cpus[0] of the affinity for the ordered consumer and host; the workers take cpus[1:]), so CPU 0, when a booking holds it,
is that job's parent CPU and the job owns it; it is never a worker CPU and never in two bookings. A day run books lowest
CPUs first (0-15 on an idle box: sixteen distinct physical cores), an ingest highest first, so the two kinds do not
fragment each other.

LAUNCH INSIDE THE BOOKING. `run` books, starts the job under `taskset -c <booked cpus>` (every worker it pins then pins
inside the booking, and every unpinned child inherits it), adds the job's pid to the booking, waits, and releases. A job
that dies without its release is reaped: a booking whose pids are all gone is released with a receipt (book reaps first).

RETAINED BOOKINGS (Step 8, 2026-10-07: a saved main day keeps its exact 16 CPUs). A day-run booking that its owner marks
`retained` (retain --booking ID --run R --day D --reason TEXT), and a booking marked OWNED by a queue day (own
--booking ID --run R --day D --attempt A, the queue's owner binding) whose pids are all gone (its holder died: reaping
RETAINS it for that owner instead of releasing it; any other booking is reaped as before), keeps its CPUs booked with
no live process: no other day can take them. Only its owner takes them back: a `book` with --cpus naming exactly that
set and --run/--day equal to the retained owner's takes the retained booking over IN PLACE (same id, the new holder
pid, the retention kept as history); any other request for those CPUs waits. An operator releases a retained booking
only with `release` and the explicit reason; nothing releases it on its own. `show` lists retained bookings with
their owner. A retained set in use by an unbooked Frankie process (an orphan of the dead holder) is not taken over
while that process runs.

STAGE CLAIMS (Greg, 2026-10-07; night: "day 1 gets ALL 32 CPUs for every step"). The stages of STAGE_SLOTS (voice: the
'adviser' slot; Jev left it on Greg's 2026-10-07 night decision "just have jev operate in that box like everyone else" and
runs --inside on the whole lane without a claim) run only --inside their day's held booking, on the slot's CPUs: SLOT_CPUS
None = EVERY CPU of the held booking (the 'adviser' slot now: the meeting runs on the whole lane like Jev, its
llama-server threads from the caller's one setting, frankie_box_experiment.MEETING_THREADS); an integer N = the N highest
WORKER CPUs of the booking (never its parent/coordinator CPU). The claim stays so two meeting children of one day (the
class worker's step and an owner school recovery's) never run at once on the lane: the second waits, visibly. A claim
is recorded under the booking's `steps` (stage, slot, cpus, pid with its start time, at) under
the ledger lock before the step runs, and moved to `steps_released` with its exit code when it ends; a claim whose pid
is gone (or never recorded within UNATTACHED_CLAIM_SECONDS) is released by the next claim. While another live claim holds
the slot, the step WAITS in place (polling every SLOT_WAIT_POLL s) and its CPU_BOOKING line names the holder and the
seconds waited. The CPU never leaves the day's booking, so no other day can take it and nothing is double booked.

OPERATIONS
  book     --kind K [--day D --run R --stage S --commit C --workers W --verify V --pid P]: book for pid P (default the
           caller's parent); prints the booking; exit 75 = waiting, 2 = refused
  run      the same, then `-- <command...>` under taskset in the booking; exit = the command's (75 waiting, 2 refused);
           --outcome FILE writes the booking outcome as JSON for the caller
  release  --booking ID [--reason TEXT]
  reap     release every booking whose pids are all gone (a retained booking is never reaped)
  own      --booking ID --run R --day D [--attempt A]: mark a live day-run booking owned by a queue day (its death
           retains it for that owner instead of reaping it)
  retain   --booking ID --run R --day D [--attempt A --reason TEXT]: mark a live day-run booking retained by its owner
           (a saved day): its CPUs stay booked after its pids end, until the owner resumes or an operator releases
  show     READ-ONLY: every CPU -> its owner (booking or unbooked Frankie process) and its live use, the free count, what
           can be booked now; --json for the raw record
  free     READ-ONLY: '<free> <online>' CPUs now (a sizing hint; the booking decides under the lock)
  allowed  --pid P: READ-ONLY, the CPUs the workers of P's job may use (its booking less the parent CPU; for a job not in
           the ledger every CPU but 0 not held by a booking), comma list; for frankie_box_spread_workers.sh
Standard library only (the spread sidecar runs it with python -I -S). Nothing here stops, signals or re-pins a running
job: `run` sets the affinity of the process it starts, and forwards SIGTERM/SIGINT/SIGHUP to it.
"""
import argparse
import datetime as dt
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

BOX = '/opt/frankie-box'
LEDGER = Path(BOX) / 'cpu-bookings'
RELEASED = LEDGER / 'released'
WAITING = LEDGER / 'waiting'
SCHEMA = 'FRANKIE_BOX_CPU_BOOKING_V1'
DAY_RUN_CPUS = 16                       # every day-run step, exactly (Greg, 2026-09-29: "Correct 16")
# Greg, 2026-10-07: "Give the day 32 CPUs and that many workers." A run may set its day slot size (plan day_cpus):
# 16 (the default, one lane) or 32 (both lanes of the main box, CPUs 0-31, ONE booking held by the day for all its
# stages). A 32 slot is never split: it waits until all 32 are free.
DAY_RUN_SIZES = (16, 32)
INGEST_CPUS = 8                         # an ingest / canary / conform day process, unless it asks a larger size
# Greg, 2026-10-07 night ("Including ingest. Basically anything using a cpu"): an ingest day process may book 8, 16, 24 or
# 32 CPUs (--size; frankie_box_ingest_block.sh DAY_CPUS): one day can take the whole box, or days side by side fill it.
# The output does not depend on the count (the encodings are pure, the replay segments are fixed by the plan, the
# reader only verifies); never split, never squeezed: a size that is not free waits like any booking.
INGEST_SIZES = (8, 16, 24, 32)
WAITING_EXIT = 75                       # EX_TEMPFAIL: not started, a later dispatch retries
REFUSED_EXIT = 2
BUSY_FRACTION = 0.05                    # an unpinned Frankie thread above this share of one CPU holds the CPU it runs on
KINDS = ('day-run', 'ingest', 'canary', 'conform')
DAY_RUN_STAGES = ('root', 'teacher', 'classroom', 'data', 'search', 'lessons', 'exchange', 'voice', 'school', 'reports',
                  'jev', 'survivors')   # survivors (stage 10): the batch boundary's survivor/candidate update, same lane rule
# THE ADVISER SLOT (Greg, 2026-10-07; widened 2026-10-07 night: "day 1 gets ALL 32 CPUs for every step"): Granite's
# meeting (the voice stage) is an ordinary stage of the day on that day's held lane, now on the WHOLE lane like Jev (it
# was ONE worker CPU at threads=1). It claims the slot (every CPU of the held booking), runs under taskset of the lane,
# and releases the claim when it ends; a second claimant waits while it is busy (the wait is printed on the step's
# CPU_BOOKING line, so it is on the stage receipt and the inspection report, never silent). No box, host, lane or
# reserved block of workers of its own. Such a stage never books on its own: it needs --inside its slot.
# JEV (Greg, 2026-10-07 night: "Give jev more"; "just have jev operate in that box like everyone else so he'll have plenty
# of cpus"): Jev is NOT a slot stage any more. He runs --inside the day's held booking like teacher, classroom, search and
# the exchange, under taskset of the WHOLE held lane (16, or 32 on a 32-CPU day), his llama-server threads from the one
# setting frankie_box_jev_cpu.JEV_THREADS. Within a day the stages run one after another (search -> jev -> lessons ->
# exchange -> voice), so Jev's lane and the meeting's slot CPU are never in use at the same time; across days each day
# has its own booking, so nothing is double booked.
STAGE_SLOTS = {'voice': 'adviser'}
SLOT_CPUS = {'adviser': None}           # None = every CPU of the day's held booking (the whole lane); N = N worker CPUs
STAGE_CPUS = {stage: SLOT_CPUS[slot] for stage, slot in STAGE_SLOTS.items()}
SLOT_WAIT_POLL = 5.0                    # seconds between claim attempts while the shared slot is busy
UNATTACHED_CLAIM_SECONDS = 120.0        # a claim whose step pid was never recorded is stale after this
INGEST_RULE = ('an ingest, canary or conform day process runs ONE pool at a time (the encode pool ends at the seal before '
               'the conformance reader starts; the parallel writer\'s replay/encode pool closes before its reader): WORKERS + 1 '
               'CPUs, the parent included; the day process books --size CPUs (one of %s, default %d) and a demand above '
               'its size is refused' % (INGEST_SIZES, INGEST_CPUS))
DAY_RUN_RULE = ('a day-run step books exactly %d CPUs, never fewer; its workers = %d (the parent keeps the lowest booked '
                'CPU); with fewer than %d free it waits' % (DAY_RUN_CPUS, DAY_RUN_CPUS - 1, DAY_RUN_CPUS))


def day_run_rule(size):
    """The day-run rule at the booking's actual size (a 32-CPU day slot states 32 and 31 workers, never 16)."""
    return ('a day-run step books exactly %d CPUs, never fewer; its workers = %d (the parent keeps the lowest booked CPU); '
            'with fewer than %d free it waits' % (size, size - 1, size))


def ingest_demand(kind, workers, verify):
    """CPUs one ingest / canary / conform day process uses: one pool at a time (2026-10-07 night: the encoders end at the
    seal, before the reader; before that an inline verify kept both pools alive and counted WORKERS x 2 + 1)."""
    return workers + 1


def ingest_workers(verify, kind='ingest', size=INGEST_CPUS):
    """The largest WORKERS whose demand fits a booking of `size` CPUs (size - 1)."""
    return max(w for w in range(0, size) if ingest_demand(kind, w, verify) <= size)


def size_of(kind, workers=None, verify=None, size=None):
    """(cpus to book, None) or (None, the refusal): the hard sizes. A day-run is DAY_RUN_CPUS unless the run set its day
    slot size (one of DAY_RUN_SIZES)."""
    if kind == 'day-run':
        if size in (None, DAY_RUN_CPUS):
            return DAY_RUN_CPUS, None
        if size not in DAY_RUN_SIZES:
            return None, 'a day-run slot is one of %s CPUs (asked %s)' % (DAY_RUN_SIZES, size)
        return size, None
    if kind not in KINDS:
        return None, 'kind must be one of %s' % ', '.join(KINDS)
    if verify not in ('inline', 'deferred') and kind != 'conform':
        return None, 'an %s booking needs --verify inline|deferred (the rule counts the verify pool)' % kind
    if workers is None or workers < 0:
        return None, 'an %s booking needs --workers (the rule counts them)' % kind
    if size is None:
        size = INGEST_CPUS
    if size not in INGEST_SIZES:
        return None, 'an %s day process books one of %s CPUs (asked %s)' % (kind, INGEST_SIZES, size)
    need = ingest_demand(kind, workers, verify)
    if need > size:
        return None, ('WORKERS=%d needs %d CPUs, more than the %d this day process books (%s); the largest WORKERS that '
                      'fits is %d (or ask a larger --size)' % (workers, need, size, INGEST_RULE,
                                                               ingest_workers(verify, kind, size)))
    return size, None


# ------------------------------------------------------------------------------------------------------------ /proc

def online_cpus():
    try:
        text = Path('/sys/devices/system/cpu/online').read_text().strip()
    except OSError:
        return list(range(os.cpu_count() or 1))
    return parse_list(text)


def parse_list(text):
    out = []
    for part in text.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            a, b = part.split('-', 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return sorted(set(out))


def cpu_list(cpus):
    return ','.join(str(c) for c in sorted(cpus))


def stat_of(path):
    """(ppid, ticks used, start time, last cpu) from /proc/<pid>[/task/<tid>]/stat, or None."""
    try:
        fields = Path(path, 'stat').read_text().rsplit(')', 1)[1].split()
        return int(fields[1]), int(fields[11]) + int(fields[12]), int(fields[19]), int(fields[36])
    except (OSError, IndexError, ValueError):
        return None


def start_time(pid):
    s = stat_of('/proc/%d' % pid)
    return s[2] if s else None


def alive(entry):
    """A booking pid is alive only when its /proc start time is the one recorded (a reused pid is another process)."""
    return start_time(entry['pid']) == entry['start']


def processes():
    """{pid: dict(ppid, exe, cmdline, cwd, comm)} of every process visible now."""
    out = {}
    for name in os.listdir('/proc'):
        if not name.isdigit():
            continue
        pid = int(name)
        s = stat_of('/proc/%d' % pid)
        if s is None:
            continue
        base = '/proc/%d/' % pid
        info = dict(ppid=s[0], exe='', cmdline='', cwd='', comm='')
        for key, read in (('exe', lambda: os.readlink(base + 'exe')), ('cwd', lambda: os.readlink(base + 'cwd')),
                          ('cmdline', lambda: Path(base + 'cmdline').read_bytes().replace(b'\0', b' ').decode('utf-8', 'replace').strip()),
                          ('comm', lambda: Path(base + 'comm').read_text().strip())):
            try:
                info[key] = read()
            except OSError:
                pass
        out[pid] = info
    return out


def is_frankie(info):
    python = os.path.basename(info['exe']).startswith('python') or info['comm'].startswith('python')
    under = (info['exe'].startswith(BOX + '/') or info['cwd'] == BOX or info['cwd'].startswith(BOX + '/')
             or BOX + '/' in info['cmdline'])
    # this ledger's own invocations (show, allowed, a book waiting on the lock) are not jobs; a booked job's tree is
    # reached through its booking instead
    return python and under and 'frankie_box_cores.py' not in info['cmdline']


def descendants(procs, roots):
    children = {}
    for pid, info in procs.items():
        children.setdefault(info['ppid'], []).append(pid)
    seen, stack = set(), [p for p in roots if p in procs]
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        stack.extend(children.get(pid, ()))
    return seen


def ancestors(procs, pid):
    out = set()
    while pid in procs and pid not in out and pid > 1:
        out.add(pid)
        pid = procs[pid]['ppid']
    return out


def threads(pids):
    """{(pid, tid): (ticks, last cpu, affinity)} of every thread of the pids."""
    out = {}
    for pid in pids:
        try:
            tids = os.listdir('/proc/%d/task' % pid)
        except OSError:
            continue
        for name in tids:
            tid = int(name)
            s = stat_of('/proc/%d/task/%d' % (pid, tid))
            if s is None:
                continue
            try:
                affinity = frozenset(os.sched_getaffinity(tid))
            except OSError:
                continue
            out[(pid, tid)] = (s[1], s[3], affinity)
    return out


def sample(pids, window):
    """[(pid, tid, busy share of one CPU over the window, last cpu, affinity)] for every thread of the pids."""
    tick = os.sysconf('SC_CLK_TCK')
    first = threads(pids)
    started = time.monotonic()
    time.sleep(max(0.2, window))
    second = threads(pids)
    elapsed = max(1e-3, time.monotonic() - started)
    rows = []
    for key, (ticks, cpu, affinity) in second.items():
        before = first.get(key, (ticks, cpu, affinity))[0]
        rows.append((key[0], key[1], max(0, ticks - before) / tick / elapsed, cpu, affinity))
    return rows


# ---------------------------------------------------------------------------------------------------------- ledger

def live_bookings():
    """[booking] of every booking file under the ledger (live or stale; stale = every pid gone)."""
    out = []
    if not LEDGER.is_dir():
        return out
    for path in sorted(LEDGER.glob('*.json')):
        try:
            b = json.loads(path.read_bytes())
        except (OSError, ValueError):
            continue
        if b.get('schema') == SCHEMA:
            b['_path'] = str(path)
            b['_alive'] = any(alive(p) for p in b.get('pids') or [])
            b['_retained'] = bool(b.get('retained'))
            out.append(b)
    return out


def write_json(path, body, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: v for k, v in body.items() if not k.startswith('_')}
    raw = json.dumps(clean, indent=1, sort_keys=True) + '\n'
    if exclusive:
        with open(path, 'x', encoding='utf-8') as out:
            out.write(raw)
        return
    tmp = path.with_name(path.name + '.pending')
    tmp.write_text(raw, encoding='utf-8')
    os.replace(tmp, path)


class Lock:
    def __enter__(self):
        LEDGER.mkdir(parents=True, exist_ok=True)
        self.handle = open(LEDGER / '.lock', 'a')
        fcntl.flock(self.handle, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        fcntl.flock(self.handle, fcntl.LOCK_UN)
        self.handle.close()


def now_iso():
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def release_one(b, reason, exit_code=None):
    """Move a booking to released/ with its release receipt (the file is kept whole, never deleted)."""
    body = dict(b, released=now_iso(), released_at=time.time(), release_reason=reason,
                pids_alive_at_release=[p['pid'] for p in b.get('pids') or [] if alive(p)])
    if exit_code is not None:
        body['exit_code'] = exit_code
    write_json(RELEASED / Path(b['_path']).name, body)
    os.remove(b['_path'])
    return body


def reap_locked():
    """Release every booking whose pids are all gone, except: a retained one (a saved day's CPUs stay its owner's), and a
    day-run booking that names its run and day, which is RETAINED for that owner instead of released (its holder died
    without a saved result: the day is unknown, its CPUs stay its own until the owner resumes or an operator releases)."""
    out = []
    for b in live_bookings():
        if b['_alive'] or b['_retained']:
            continue
        if b.get('owner'):
            # a queue day's slot that its owner marked owned (frankie_box_frankie_queue._bind_owner): never freed by the
            # holder's death; retained for that owner (the day is unknown until its ACTION=resume)
            _retain_locked(b, b['owner']['run'], b['owner']['day'], attempt=b['owner'].get('attempt'),
                           reason='reaped: every pid of the booking is gone without a release; retained for its owner (unknown)')
            continue
        out.append(release_one(b, 'reaped: every pid of the booking is gone (the job ended without its release)'))
    return out


def _retain_locked(b, run, day, attempt=None, reason=None):
    """Under the lock: the booking marked retained; its pids are moved aside (a retained booking has no live process by
    definition: its day's steps ended), so it reads as not alive everywhere while its CPUs stay booked."""
    if b.get('retained') and (b['retained'].get('run'), b['retained'].get('day')) != (run, day):
        raise ValueError('booking %s is retained by %s %s already' % (b['booking'], b['retained'].get('run'), b['retained'].get('day')))
    if not b.get('retained'):
        b['retained'] = dict(run=run, day=day, attempt=attempt, reason=reason, at=now_iso(), at_epoch=time.time(),
                             by_pid=os.getpid(), pids_at_retain=b.get('pids') or [])
        b['pids'] = []
    elif attempt and not b['retained'].get('attempt'):
        b['retained']['attempt'] = attempt
    write_json(b['_path'] if '_path' in b else LEDGER / (b['booking'] + '.json'), b)
    return b


def attribution(procs, bookings):
    """{pid: booking id} for every process that is a booking pid or a descendant of one (the job's tree)."""
    owner = {}
    # a step's own pid first (a held day slot's steps are attached to it), then the holders: every slot of the ROOT-line
    # worker shares one holder pid, so its descendants would otherwise all read as the first slot's
    for holders in (False, True):
        for b in bookings:
            roots = [p['pid'] for p in b.get('pids') or [] if alive(p) and (p.get('role') == 'booking holder') == holders]
            for pid in descendants(procs, roots):
                owner.setdefault(pid, b['booking'])
    return owner


def usage(window, exclude=()):
    """(held, rows, procs, bookings): held = {cpu: [holder]} of the Frankie processes NOT in the ledger; rows = every
    sampled Frankie thread with its owner (booking id or None)."""
    online = frozenset(online_cpus())
    procs = processes()
    bookings = [b for b in live_bookings() if b['_alive'] or b['_retained']]   # a retained booking holds its CPUs
    owner = attribution(procs, bookings)
    frankie = descendants(procs, [pid for pid, info in procs.items() if is_frankie(info)])
    frankie |= set(owner)
    frankie -= set(exclude)
    held, rows = {}, []
    for pid, tid, busy, cpu, affinity in sample(sorted(frankie), window):
        who = owner.get(pid)
        rows.append(dict(pid=pid, tid=tid, busy=round(busy, 3), cpu=cpu, affinity=cpu_list(affinity),
                         pinned=affinity != online, booking=who, command=procs.get(pid, {}).get('cmdline', '')[:160]))
        if who is not None:
            continue
        holder = dict(pid=pid, tid=tid, command=procs.get(pid, {}).get('cmdline', '')[:160])
        if affinity != online:
            for c in affinity:
                held.setdefault(c, []).append(dict(holder, why='pinned to %s' % cpu_list(affinity)))
        elif busy >= BUSY_FRACTION:
            held.setdefault(cpu, []).append(dict(holder, why='running here at %d%% of a CPU' % round(100 * busy)))
    return held, rows, procs, bookings


def book_locked(kind, size, pid, meta, window):
    """Under the lock: reap, then book `size` free CPUs for pid, or return the waiting record."""
    reaped = reap_locked()
    me = os.getpid()
    procs_now = processes()
    exclude = ancestors(procs_now, me) | {me}
    held, _, procs, bookings = usage(window, exclude=exclude)
    online = online_cpus()
    booked = {c for b in bookings for c in b['cpus']}
    free = [c for c in online if c not in booked and c not in held]
    if size > len(online):
        return None, dict(status='refused', reason='%d CPUs asked, the box has %d' % (size, len(online)))
    requested = meta.get('cpus')
    if requested is not None:
        if len(requested) != size or len(set(requested)) != size or not set(requested).issubset(online):
            return None, dict(status='refused', reason='retained lane CPU set differs from this box')
        if not set(requested).issubset(free):
            # the owner of a RETAINED booking of exactly this set takes it back IN PLACE (one record replaced, never a
            # moment with the CPUs free or double booked): the same booking id, the new holder pid, the retention kept
            # as its history; anyone else waits
            mine = [b for b in bookings if b['_retained'] and sorted(b['cpus']) == sorted(requested)
                    and (b.get('retained') or {}).get('run') == meta.get('run')
                    and (b.get('retained') or {}).get('day') == meta.get('day')]
            if not mine:
                return None, dict(status='waiting', reason='the retained lane CPU set is still occupied')
            orphan = sorted(c for c in requested if c in held)
            if orphan:
                return None, dict(status='waiting', in_use_unbooked=cpu_list(orphan),
                                  reason='the retained lane CPU set is in use by a Frankie process not in the ledger (CPUs %s; '
                                         'an orphan of the dead holder?): not taken over while it runs' % cpu_list(orphan))
            start = start_time(pid)
            if start is None:
                return None, dict(status='refused', reason='pid %d is not running' % pid)
            b = mine[0]
            b['resumed'] = (b.get('resumed') or []) + [dict(retained=b.pop('retained'), at=now_iso(), at_epoch=time.time(),
                                                           stage=meta.get('stage'), commit=meta.get('commit'), pid=pid)]
            b['_retained'] = False
            b['pids'] = [dict(pid=pid, start=start, role='booking holder')]
            b['stage'] = meta.get('stage')
            b['commit'] = meta.get('commit') or b.get('commit')
            write_json(b['_path'], b)
            return b, dict(status='booked', booking=b['booking'], cpus=cpu_list(b['cpus']), parent_cpu=b['parent_cpu'],
                           resumed_from=b['booking'])
    if len(free) < size:
        return None, dict(status='waiting', free=len(free), needed=size, free_cpus=cpu_list(free),
                          booked_cpus=cpu_list(booked), in_use_unbooked=cpu_list(held), reaped=[r['booking'] for r in reaped],
                          reason='waiting: %d free of %d needed (booked by the ledger: %s; in use by Frankie processes not '
                                 'in the ledger: %s)' % (len(free), size, cpu_list(booked) or 'none', cpu_list(held) or 'none'))
    cpus = sorted(requested if requested is not None else (free[:size] if kind == 'day-run' else free[-size:]))
    stamp = time.time()
    booking = '%s-%s-%s-%d-%d' % (kind, re.sub('[^A-Za-z0-9_]', '_', meta.get('day') or 'box'),
                                  re.sub('[^A-Za-z0-9_]', '_', meta.get('stage') or kind), int(stamp), pid)
    start = start_time(pid)
    if start is None:
        return None, dict(status='refused', reason='pid %d is not running' % pid)
    body = dict(schema=SCHEMA, booking=booking, kind=kind, day=meta.get('day'), run=meta.get('run'), stage=meta.get('stage'),
                commit=meta.get('commit'), cpus=cpus, cpu_list=cpu_list(cpus), parent_cpu=cpus[0], owns_cpu0=cpus[0] == 0,
                worker_cpus=cpus[1:], size=size, workers=meta.get('workers'), verify=meta.get('verify'),
                rule=day_run_rule(size) if kind == 'day-run' else INGEST_RULE,
                demand=(size if kind == 'day-run' else ingest_demand(kind, meta.get('workers') or 0, meta.get('verify'))),
                pids=[dict(pid=pid, start=start, role='booking holder')], started=now_iso(), started_at=stamp,
                nproc=len(online), free_before=len(free), booked_before=cpu_list(booked), in_use_unbooked_before=cpu_list(held),
                reaped_before=[r['booking'] for r in reaped], host=os.uname().nodename)
    body['_path'] = str(LEDGER / (booking + '.json'))
    write_json(body['_path'], body, exclusive=True)
    return body, dict(status='booked', booking=booking, cpus=cpu_list(cpus), parent_cpu=cpus[0])


def record_waiting(kind, meta, outcome):
    body = dict(schema='FRANKIE_BOX_CPU_BOOKING_WAITING_V1', kind=kind, at=now_iso(), **{k: meta.get(k) for k in
                ('day', 'run', 'stage', 'commit', 'workers', 'verify')}, **outcome)
    name = '%s-%s-%s-%d.json' % (time.strftime('%Y%m%dT%H%M%S', time.gmtime()), kind,
                                 re.sub('[^A-Za-z0-9_]', '_', meta.get('day') or 'box'), os.getpid())
    try:
        write_json(WAITING / name, body, exclusive=True)
        return str(WAITING / name)
    except OSError:
        return None


def book(kind, pid, meta, window):
    size, why = size_of(kind, meta.get('workers'), meta.get('verify'), meta.get('size'))
    if not why and kind == 'day-run' and meta.get('cpus') and len(meta['cpus']) != size:
        # a saved day's resume books exactly its retained set: its size is that set's size
        size, why = (len(meta['cpus']), None) if len(meta['cpus']) in DAY_RUN_SIZES else (
            None, 'a retained day-run set of %d CPUs is not one of %s' % (len(meta['cpus']), DAY_RUN_SIZES))
    if why:
        return None, dict(status='refused', reason=why)
    with Lock():
        b, outcome = book_locked(kind, size, pid, meta, window)
    if outcome['status'] == 'waiting':
        outcome['record'] = record_waiting(kind, meta, outcome)
    return b, outcome


def attach(booking, pid, role):
    with Lock():
        path = LEDGER / (booking + '.json')
        b = json.loads(path.read_bytes())
        start = start_time(pid)
        if start is not None:
            b['pids'].append(dict(pid=pid, start=start, role=role))
            write_json(path, b)


def own(booking, run, day, attempt):
    """Mark a live day-run booking OWNED by a queue day (run, day, attempt): from now on its death retains it for that
    owner instead of reaping it. Returns the booking."""
    with Lock():
        path = LEDGER / (booking + '.json')
        if not path.is_file():
            raise ValueError('booking %s is not in the ledger (released or never made)' % booking)
        b = json.loads(path.read_bytes())
        if b.get('kind') != 'day-run':
            raise ValueError('only a day-run booking is owned (%s is %s)' % (booking, b.get('kind')))
        if b.get('owner') and (b['owner'].get('run'), b['owner'].get('day')) != (run, day):
            raise ValueError('booking %s is owned by %s %s already' % (booking, b['owner'].get('run'), b['owner'].get('day')))
        b['owner'] = dict(run=run, day=day, attempt=attempt, at=now_iso())
        write_json(path, b)
        return b


def retain(booking, run, day, attempt=None, reason=None):
    """Mark a day-run booking retained by its owner (run, day): it survives its pids and reaping; only the owner's
    resume (a book of exactly its CPUs for the same run/day) or an explicit release ends it. Returns the booking."""
    with Lock():
        path = LEDGER / (booking + '.json')
        if not path.is_file():
            raise ValueError('booking %s is not in the ledger (released or never made)' % booking)
        b = json.loads(path.read_bytes())
        b['_path'] = str(path)
        if b.get('kind') != 'day-run':
            raise ValueError('only a day-run booking is retained (%s is %s)' % (booking, b.get('kind')))
        if b.get('run') not in (None, run) or b.get('day') not in (None, day):
            raise ValueError('booking %s belongs to %s %s, not %s %s' % (booking, b.get('run'), b.get('day'), run, day))
        return _retain_locked(b, run, day, attempt=attempt, reason=reason)


def release(booking, reason, exit_code=None):
    with Lock():
        path = LEDGER / (booking + '.json')
        if not path.is_file():
            return None
        b = json.loads(path.read_bytes())
        b['_path'] = str(path)
        return release_one(b, reason, exit_code)


# -------------------------------------------------------------------------------------------------------- commands

def meta_of(a):
    meta = dict(day=a.day, run=a.run, stage=a.stage, commit=a.commit, workers=a.workers, verify=a.verify,
                size=getattr(a, 'size', None))
    if getattr(a, 'cpus', None):
        meta['cpus'] = parse_list(a.cpus)       # the retained lane CPU set, exactly (a saved day's resume)
    return meta


def emit_outcome(a, outcome):
    if getattr(a, 'outcome', None):
        write_json(a.outcome, outcome)
    tag = dict(booked='CPU_BOOKING', waiting='CPU_BOOKING_WAITING', refused='CPU_BOOKING_REFUSED')[outcome['status']]
    print('%s %s' % (tag, outcome.get('reason') or json.dumps(outcome, sort_keys=True)), flush=True)
    if outcome['status'] != 'booked':
        print(json.dumps(outcome, indent=1, sort_keys=True), flush=True)


def cmd_book(a):
    b, outcome = book(a.kind, a.pid or os.getppid(), meta_of(a), a.window)
    emit_outcome(a, outcome)
    if b:
        print(json.dumps({k: v for k, v in b.items() if not k.startswith('_')}, indent=1, sort_keys=True))
        return 0
    return WAITING_EXIT if outcome['status'] == 'waiting' else REFUSED_EXIT


def held_booking(booking):
    """The live booking `booking` (its file read under the lock), or (None, why)."""
    with Lock():
        path = LEDGER / (booking + '.json')
        if not path.is_file():
            return None, 'booking %s is not in the ledger (released or never made)' % booking
        b = json.loads(path.read_bytes())
        if b.get('retained'):
            return None, 'booking %s is retained by its owner %s %s (no live step; ACTION=resume brings it back)' % (
                booking, b['retained'].get('run'), b['retained'].get('day'))
        if not any(alive(p) for p in b.get('pids') or []):
            return None, 'booking %s has no live pid (its holder is gone)' % booking
        return b, None


def claim_step(booking, stage):
    """Under the ledger lock: claim the stage's slot CPU(s) of the live held booking (STAGE_SLOTS): every CPU of the
    booking when SLOT_CPUS is None (the whole lane), else the highest worker CPU(s) of the booking; shared by every stage
    of the same slot. Stale claims (pid gone, or never attached within
    UNATTACHED_CLAIM_SECONDS) are moved to steps_released first. Returns (claim, None, None), or (None, why, holder) while
    another live claim holds the slot, or (None, why, None) when the booking is not a live held slot."""
    slot = STAGE_SLOTS[stage]
    with Lock():
        path = LEDGER / (booking + '.json')
        if not path.is_file():
            return None, 'booking %s is not in the ledger (released or never made)' % booking, None
        b = json.loads(path.read_bytes())
        if b.get('retained') or not any(alive(p) for p in b.get('pids') or []):
            return None, 'booking %s is not a live held slot' % booking, None
        steps, gone, now = [], [], time.time()
        for s in b.get('steps') or []:
            stale = (not alive(s['pid'])) if s.get('pid') else (now - float(s.get('at_epoch') or 0) > UNATTACHED_CLAIM_SECONDS)
            (gone if stale else steps).append(s)
        for s in gone:
            s.update(released=now_iso(), release_reason='stale: its pid is gone or was never recorded (released by the next claim)')
        count = SLOT_CPUS[slot]
        if count is None:
            cpus = sorted(b['cpus'])        # the whole held lane (Greg, 2026-10-07 night: every step gets the day's CPUs)
        else:
            workers = sorted(c for c in (b.get('worker_cpus') or b['cpus'][1:]) if c != b['parent_cpu'])
            if len(workers) < count:
                return None, 'the held slot %s has %d worker CPU(s); the %s slot needs %d' % (booking, len(workers), slot, count), None
            cpus = workers[-count:]
        holders = [s for s in steps if s.get('slot') == slot or set(s.get('cpus') or []) & set(cpus)]
        if gone:
            b['steps'] = steps
            b['steps_released'] = (b.get('steps_released') or []) + gone
            write_json(path, b)
        if holders:
            h = holders[0]
            return None, ('the %s slot (CPU %s of %s) is held by stage %s (claim %s since %s)'
                          % (slot, cpu_list(cpus), booking, h.get('stage'), h.get('claim_id'), h.get('at'))), h
        claim = dict(stage=stage, slot=slot, cpus=cpus, pid=None, at=now_iso(), at_epoch=now,
                     claim_id='%s-%d-%d' % (stage, int(now * 1000), os.getpid()))
        b['steps'] = steps + [claim]
        write_json(path, b)
        return claim, None, None


def attach_step(booking, claim_id, pid, exit_code=None, end=False):
    """Record the step's pid on its claim, or (end=True) move the claim to steps_released with its exit code."""
    with Lock():
        path = LEDGER / (booking + '.json')
        if not path.is_file():
            return None
        b = json.loads(path.read_bytes())
        keep, done = [], None
        for s in b.get('steps') or []:
            if s.get('claim_id') != claim_id:
                keep.append(s)
            elif end:
                done = dict(s, released=now_iso(), exit_code=exit_code, release_reason='the step ended')
            else:
                start = start_time(pid)
                keep.append(dict(s, pid=dict(pid=pid, start=start) if start is not None else None))
        b['steps'] = keep
        if done is not None:
            b['steps_released'] = (b.get('steps_released') or []) + [done]
        write_json(path, b)
        return b


def cmd_run_inside(a, command):
    """A step of a day that already HOLDS its day-run booking (Greg, 2026-09-30: a day never leaves its slot until every
    kept step of the run table is done): the step runs under taskset of the held CPUs, its pid is added to the booking,
    nothing is booked or released here (the slot's holder releases it when the whole day is done); Jev too, on the whole
    lane. A STAGE_CPUS step (the meeting, voice) runs on its claimed CPUs (the whole lane: SLOT_CPUS None) and gives the
    claim back when it ends."""
    b, why = held_booking(a.inside)
    if b is None:
        emit_outcome(a, dict(status='refused', reason=why))
        return REFUSED_EXIT
    if a.stage in STAGE_CPUS:
        return cmd_run_step(a, b, command)
    emit_outcome(a, dict(status='booked', booking=b['booking'], cpus=b['cpu_list'], parent_cpu=b['parent_cpu'],
                         inside=True, reason='inside the day\'s held slot %s: CPUs %s' % (b['booking'], b['cpu_list'])))
    print('### inside the held day slot %s: CPUs %s (stage %s)' % (b['booking'], b['cpu_list'], a.stage), flush=True)
    # FRANKIE_LANE_CPUS too (the held lane's CPUs, the name boss_session/granite read first), so every stage child sees
    # the day's full lane list, never the host count (Greg, 2026-10-07: everything pinned for day 1)
    env = dict(os.environ, FRANKIE_CPU_BOOKING=b['booking'], FRANKIE_BOOKED_CPUS=b['cpu_list'], FRANKIE_LANE_CPUS=b['cpu_list'])
    try:
        child = subprocess.Popen(['taskset', '-c', b['cpu_list']] + command, env=env)
    except OSError as error:
        print('### the step did not start (%s); the slot stays held' % error, flush=True)
        return 1
    try:
        attach(b['booking'], child.pid, 'step %s (under taskset, inside the held slot)' % (a.stage or '?'))
    except (OSError, ValueError, KeyError) as error:
        print('### the step pid %d was not added to the booking (%s)' % (child.pid, error), flush=True)

    def forward(signum, _frame):
        if child.poll() is None:
            child.send_signal(signum)
    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(s, forward)
    code = child.wait()
    return 128 - code if code < 0 else code


def cmd_run_step(a, b, command):
    """A STAGE_SLOTS step inside its day's held slot: claim the slot's CPUs (the whole lane for SLOT_CPUS None; waiting
    in place while another stage of the slot holds it, the wait recorded), run under taskset of exactly those CPUs,
    release the claim when it ends (the day's slot itself stays held)."""
    started, waited_on, announced = time.time(), None, False
    while True:
        claim, why, holder = claim_step(b['booking'], a.stage)
        if claim is not None:
            break
        if holder is None:
            emit_outcome(a, dict(status='refused', reason=why))
            return REFUSED_EXIT
        waited_on = dict(stage=holder.get('stage'), claim=holder.get('claim_id'), since=holder.get('at'))
        if not announced:
            print('### stage %s waits for the shared slot: %s' % (a.stage, why), flush=True)
            announced = True
        time.sleep(SLOT_WAIT_POLL)
    waited = round(time.time() - started, 1)
    cpus = cpu_list(claim['cpus'])
    emit_outcome(a, dict(status='booked', booking=b['booking'], cpus=cpus, parent_cpu=b['parent_cpu'], inside=True,
                         step_claim=claim['claim_id'], slot=claim['slot'], waited_seconds=waited, waited_on=waited_on,
                         reason='stage %s inside the day\'s held slot %s on the %s slot CPUs %s (the lane is %s); waited '
                                '%.1f s for the slot%s' % (a.stage, b['booking'], claim['slot'], cpus, b['cpu_list'], waited,
                                                          (' (held by stage %s)' % waited_on['stage']) if waited_on else '')))
    print('### stage %s inside the held day slot %s: CPU(s) %s of %s (claim %s)'
          % (a.stage, b['booking'], cpus, b['cpu_list'], claim['claim_id']), flush=True)
    env = dict(os.environ, FRANKIE_CPU_BOOKING=b['booking'], FRANKIE_BOOKED_CPUS=cpus, FRANKIE_LANE_CPUS=b['cpu_list'],
               FRANKIE_STEP_CLAIM=claim['claim_id'])
    try:
        child = subprocess.Popen(['taskset', '-c', cpus] + command, env=env)
    except OSError as error:
        attach_step(b['booking'], claim['claim_id'], None, exit_code=None, end=True)
        print('### the step did not start (%s); its claim is released, the slot stays held' % error, flush=True)
        return 1
    try:
        attach_step(b['booking'], claim['claim_id'], child.pid)
    except (OSError, ValueError, KeyError) as error:
        print('### the step pid %d was not recorded on its claim (%s)' % (child.pid, error), flush=True)

    def forward(signum, _frame):
        if child.poll() is None:
            child.send_signal(signum)
    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(s, forward)
    code = child.wait()
    code = 128 - code if code < 0 else code
    try:
        attach_step(b['booking'], claim['claim_id'], None, exit_code=code, end=True)
        print('### stage %s claim %s released (exit %d); the slot stays held' % (a.stage, claim['claim_id'], code), flush=True)
    except (OSError, ValueError, KeyError) as error:
        print('### stage %s claim %s not released here (%s); the next claim releases it once its pid is gone'
              % (a.stage, claim['claim_id'], error), flush=True)
    return code


def cmd_run(a):
    command = a.command[1:] if a.command[:1] == ['--'] else a.command
    if not command:
        print('run needs -- <command...>', file=sys.stderr)
        return REFUSED_EXIT
    if getattr(a, 'inside', None):
        return cmd_run_inside(a, command)
    if a.stage in STAGE_CPUS:
        emit_outcome(a, dict(status='refused', reason='stage %s runs only inside its day\'s held lane (--inside) on the shared '
                                                      '%s slot; it never books CPUs of its own' % (a.stage, STAGE_SLOTS[a.stage])))
        return REFUSED_EXIT
    b, outcome = book(a.kind, os.getpid(), meta_of(a), a.window)
    if not b:
        emit_outcome(a, outcome)
        return WAITING_EXIT if outcome['status'] == 'waiting' else REFUSED_EXIT
    outcome.update(rule=b['rule'], workers=b['workers'], verify=b['verify'], nproc=b['nproc'])
    emit_outcome(a, outcome)
    print('### CPU booking %s: CPUs %s (parent CPU %d, %d worker CPUs); %s'
          % (b['booking'], b['cpu_list'], b['parent_cpu'], len(b['worker_cpus']), b['rule']), flush=True)
    env = dict(os.environ, FRANKIE_CPU_BOOKING=b['booking'], FRANKIE_BOOKED_CPUS=b['cpu_list'], FRANKIE_LANE_CPUS=b['cpu_list'])
    try:
        child = subprocess.Popen(['taskset', '-c', b['cpu_list']] + command, env=env)
    except OSError as error:
        release(b['booking'], 'the job did not start (%s)' % error)
        print('### CPU booking %s released: the job did not start (%s)' % (b['booking'], error), flush=True)
        return 1
    try:
        attach(b['booking'], child.pid, 'job (under taskset)')
    except (OSError, ValueError, KeyError) as error:
        print('### the job pid %d was not added to the booking (%s); the run process stays its holder'
              % (child.pid, error), flush=True)

    def forward(signum, _frame):
        if child.poll() is None:
            child.send_signal(signum)
    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(s, forward)
    code = child.wait()
    code = 128 - code if code < 0 else code
    release(b['booking'], 'the job ended (exit %d)' % code, exit_code=code)
    print('### CPU booking %s released (exit %d)' % (b['booking'], code), flush=True)
    return code


def cmd_own(a):
    b = own(a.booking, a.run, a.day, a.attempt)
    print(json.dumps({k: v for k, v in b.items() if not k.startswith('_')}, indent=1, sort_keys=True))
    return 0


def cmd_retain(a):
    b = retain(a.booking, a.run, a.day, attempt=a.attempt, reason=a.reason or 'retained by its owner (a saved day)')
    print(json.dumps({k: v for k, v in b.items() if not k.startswith('_')}, indent=1, sort_keys=True))
    return 0


def cmd_release(a):
    r = release(a.booking, a.reason or 'released by hand')
    print(json.dumps({k: v for k, v in (r or {}).items() if not k.startswith('_')} or dict(missing=a.booking),
                     indent=1, sort_keys=True))
    return 0 if r else 1


def cmd_reap(_a):
    with Lock():
        reaped = reap_locked()
    print(json.dumps(dict(reaped=[r['booking'] for r in reaped], receipts=[str(RELEASED / (r['booking'] + '.json'))
                                                                           for r in reaped]), indent=1, sort_keys=True))
    return 0


def cmd_allowed(a):
    """READ-ONLY. The CPUs the workers of a's pid may use, comma list (empty = none)."""
    procs = processes()
    chain = ancestors(procs, a.pid)
    bookings = [b for b in live_bookings() if b['_alive']]
    for b in bookings:
        if any(p['pid'] in chain and alive(p) for p in b['pids']):
            print(cpu_list(b['cpus'][1:]))
            return 0
    booked = {c for b in bookings for c in b['cpus']}
    print(cpu_list(c for c in online_cpus() if c != 0 and c not in booked))
    return 0


def cmd_free(a):
    """READ-ONLY. '<free> <online>': the CPUs a booking could take now (online less booked less in use by unbooked Frankie
    processes, the same sets book uses). A hint for sizing (frankie_box_ingest_block.sh DAY_CPUS=auto); the booking itself
    decides under the lock."""
    me = os.getpid()
    held, _, _, bookings = usage(a.window, exclude=ancestors(processes(), me) | {me})
    online = online_cpus()
    booked = {c for b in bookings for c in b['cpus']}
    print('%d %d' % (len([c for c in online if c not in booked and c not in held]), len(online)))
    return 0


def cmd_show(a):
    """READ-ONLY: every CPU -> owner, live use, free count. Writes nothing (a stale booking is named, not reaped)."""
    me = os.getpid()
    procs_now = processes()
    all_bookings = live_bookings()
    stale = [b for b in all_bookings if not b['_alive'] and not b['_retained']]
    retained = [b for b in all_bookings if b['_retained']]
    held, rows, procs, bookings = usage(a.window, exclude=ancestors(procs_now, me) | {me})
    online = online_cpus()
    by_cpu = {}
    for b in bookings:
        for c in b['cpus']:
            by_cpu.setdefault(c, []).append(b)
    live = {}
    for r in rows:
        if r['busy'] >= BUSY_FRACTION:
            live.setdefault(r['cpu'], []).append(r)
    holders = {p['pid'] for b in bookings for p in b['pids'] if p.get('role') == 'booking holder'}
    outside = []
    for r in rows:
        if r['booking'] is None or r['pid'] in holders:
            continue
        b = next(x for x in bookings if x['booking'] == r['booking'])
        aff = set(parse_list(r['affinity']))
        if not aff <= set(b['cpus']) or (r['busy'] >= BUSY_FRACTION and r['cpu'] not in b['cpus']):
            outside.append(dict(r, booked=b['cpu_list']))
    free = [c for c in online if c not in by_cpu and c not in held]
    lines = ['### CPU ledger %s (%s), %d online CPUs, sampled %.1f s; read-only' % (LEDGER, os.uname().nodename,
                                                                                  len(online), a.window)]
    for c in online:
        owners = by_cpu.get(c, [])
        if len(owners) > 1:
            who = 'DOUBLE BOOKED: ' + ', '.join(b['booking'] for b in owners)
        elif owners:
            b = owners[0]
            who = 'booking %s (%s%s, day %s, run %s)%s%s' % (b['booking'], b['kind'], ' ' + b['stage'] if b.get('stage') and
                                                            b['stage'] != b['kind'] else '', b.get('day'), b.get('run'),
                                                            ' PARENT' if c == b['parent_cpu'] else '',
                                                            ' RETAINED' if b['_retained'] and not b['_alive'] else '')
        elif c in held:
            h = held[c][0]
            who = 'IN USE, not in the ledger: pid %d (%s) %s%s' % (h['pid'], h['command'][:70], h['why'],
                                                                  ' +%d more' % (len(held[c]) - 1) if len(held[c]) > 1 else '')
        else:
            who = 'free'
        use = ', '.join('pid %d/%d %d%%' % (r['pid'], r['tid'], round(100 * r['busy'])) for r in
                        sorted(live.get(c, []), key=lambda r: -r['busy'])[:4]) or 'idle'
        lines.append('CPU %2d  %-100s  live: %s' % (c, who[:100], use))
    lines.append('free: %d of %d (%s)' % (len(free), len(online), cpu_list(free) or 'none'))
    lines.append('a day run (%d) can book now: %s; ingest day processes (%d each) that can book now: %d'
                 % (DAY_RUN_CPUS, 'yes' if len(free) >= DAY_RUN_CPUS else 'no, waiting: %d free of %d needed'
                    % (len(free), DAY_RUN_CPUS), INGEST_CPUS, len(free) // INGEST_CPUS))
    for b in stale:
        lines.append('STALE booking %s (CPUs %s): every pid gone; the next book or ACTION=reap releases it'
                     % (b['booking'], b['cpu_list']))
    for b in retained:
        r = b.get('retained') or {}
        lines.append('RETAINED booking %s (CPUs %s) by %s %s attempt %s since %s (%s): %s; only its owner\'s resume or an '
                     'explicit release ends it' % (b['booking'], b['cpu_list'], r.get('run'), r.get('day'), r.get('attempt'),
                                                   r.get('at'), r.get('reason'), 'its holder is alive' if b['_alive']
                                                   else 'every pid gone, the CPUs stay booked'))
    for r in outside:
        lines.append('OUTSIDE ITS BOOKING: pid %d/%d of %s on CPU %d, affinity %s, booked %s'
                     % (r['pid'], r['tid'], r['booking'], r['cpu'], r['affinity'], r['booked']))
    lines.append('rules: %s. %s.' % (DAY_RUN_RULE, INGEST_RULE))
    print('\n'.join(lines))
    if a.json:
        print(json.dumps(dict(bookings=[{k: v for k, v in b.items() if not k.startswith('_')} for b in bookings],
                              stale=[b['booking'] for b in stale], retained=[b['booking'] for b in retained],
                              in_use_unbooked={str(k): v for k, v in held.items()},
                              free=free, outside=outside, threads=rows), indent=1, sort_keys=True))
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='action', required=True)
    for name in ('book', 'run'):
        s = sub.add_parser(name)
        s.add_argument('--kind', required=True, choices=KINDS)
        s.add_argument('--day')
        s.add_argument('--run')
        s.add_argument('--stage')
        s.add_argument('--commit')
        s.add_argument('--workers', type=int)
        s.add_argument('--verify', choices=('inline', 'deferred'))
        s.add_argument('--window', type=float, default=1.0, help='seconds between the two /proc samples')
        s.add_argument('--outcome', help='write the booking outcome (booked | waiting | refused) as JSON here')
        s.add_argument('--cpus', help='a saved day\'s resume: exactly its retained CPU list (comma list / ranges)')
        s.add_argument('--size', type=int, help='day-run slot size: one of %s (default %d; the run\'s plan day_cpus); '
                                                'an ingest/canary/conform day process: one of %s (default %d)'
                                                % (DAY_RUN_SIZES, DAY_RUN_CPUS, INGEST_SIZES, INGEST_CPUS))
        if name == 'book':
            s.add_argument('--pid', type=int, help='the process that holds the booking (default: the caller\'s parent)')
        else:
            s.add_argument('--inside', help='run inside this live day-run booking (the day\'s held slot): no booking, '
                                            'no release')
            s.add_argument('command', nargs=argparse.REMAINDER, help='-- the command to run under taskset')
    s = sub.add_parser('release')
    s.add_argument('--booking', required=True)
    s.add_argument('--reason')
    for name in ('retain', 'own'):
        s = sub.add_parser(name)
        s.add_argument('--booking', required=True)
        s.add_argument('--run', required=True)
        s.add_argument('--day', required=True)
        s.add_argument('--attempt')
        if name == 'retain':
            s.add_argument('--reason')
    sub.add_parser('reap')
    s = sub.add_parser('show')
    s.add_argument('--window', type=float, default=2.0)
    s.add_argument('--json', action='store_true')
    s = sub.add_parser('allowed')
    s.add_argument('--pid', type=int, required=True)
    s = sub.add_parser('free')
    s.add_argument('--window', type=float, default=1.0)
    a = p.parse_args()
    if getattr(a, 'booking', None) and not re.fullmatch('[A-Za-z0-9_.-]{1,160}', a.booking):
        raise SystemExit('--booking: a booking id from the ledger')
    if getattr(a, 'inside', None) and not re.fullmatch('[A-Za-z0-9_.-]{1,160}', a.inside):
        raise SystemExit('--inside: a booking id from the ledger')
    if getattr(a, 'cpus', None):
        try:
            parse_list(a.cpus)
        except (ValueError, TypeError):
            raise SystemExit('--cpus: a comma list of CPUs / ranges')
    return dict(book=cmd_book, run=cmd_run, release=cmd_release, retain=cmd_retain, own=cmd_own, reap=cmd_reap, show=cmd_show,
                allowed=cmd_allowed, free=cmd_free)[a.action](a)


if __name__ == '__main__':
    sys.exit(main())
