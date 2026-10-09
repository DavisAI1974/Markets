"""The hub DOCTOR (Greg, 2026-10-09 session 12, HUB DESIGN at the top of CLAUDE.md: "A DEAD PIECE IS REVIVED, NEVER
SKIPPED"). If a piece dies mid-turn, the hub core takes its lock over and records it ('takeover'), the pieces that
need it keep WAITING (a waiter is eligible only once each of its PREREQUISITES, hub.json `prerequisites`, has written the
round, so a death never releases the pieces that depend on it), and this doctor resumes the dead piece from ITS OWN save
so it finishes its part. Dependents never proceed on a partial part.

What the doctor does, and only this:
  - it watches one hub (frankie_box_hub.py) EVENT-DRIVEN: inotify on the hub directory and its pieces/ directory (an
    events.jsonl line, a turn.json replace, a turn.lock removal, a piece's write each wake it) and a pidfd on the turn's
    holder, on every live waiter and on every process the doctor started (an exit wakes it). No sleep, no timed poll, no
    bounded wait, no timeout anywhere: every wait is Waiter.wait() with no argument (counted; the count is in the
    'doctor-stopped' event).
  - it reacts to (1) a holder whose pid is gone (the pidfd fires, or a 'takeover' event naming the dead piece and pid);
    (2) a waiter whose pid is gone (still listed in turn.json, or already pruned as 'waiter-gone' by the core) when that
    piece has not written the current round; (3) a process it started for a piece that IS the piece (a standalone spoke)
    exiting before the piece wrote the round. Each death (piece, dead pid) is handled ONCE: 'doctor-revive-requested'
    (piece, dead_pid, round, cause), then revive(). Nothing else is acted on.
  - revive(hub_dir, piece) looks the piece up in REVIVERS (how that piece is resumed from its own save on this box),
    starts it DETACHED (systemd-run without CPUAffinity when systemd runs, else subprocess.Popen with start_new_session;
    the method is recorded) and records 'doctor-revived' with the new pid and the revive count for that piece. A piece
    that dies again is revived again, each time with the next count: no cap, no backoff timer; the count makes a loop
    visible in the events. A piece with no reviver is 'doctor-no-reviver' (the known pieces listed) and the doctor keeps
    watching.
  - it never takes the turn, never writes a piece's file, never recomputes anything and never edits hub.json or
    turn.json: the revived piece's own take_turn performs the core's takeover and its own write carries its part. The
    doctor's only writes are event lines in the hub's events.jsonl and its own state directory beside the hub
    (<hub_root>/<run>/<day>.doctor/: the single-instance lock and the revived processes' logs; outside the hub directory,
    so the hub's clean() never sees it).
  - nothing silent: every action and every failure is an event line ('doctor-error' with the exception text); a repeated
    identical scan failure is recorded once (a doctor event wakes the doctor itself, so re-recording would spin).

REVIVERS (explicit and extensible; a --revivers JSON file {piece: spec | null} replaces or removes entries, and
register(piece, spec) does the same in code). A spec: {"argv": [...], "env": {...}, "process_is_piece": bool, "note"}.
argv and env values are formatted with {hub_dir} {piece} {run} {day} {round} {python} {box} {code_root}
(code_root = readlink -f /opt/frankie-box/code/current, resolved only when a spec names it; the queue script is looked for
there and under its markets/ checkout; absent = a 'doctor-error', the revive not started).
  root, teacher, classroom, teacher-2, exchange, jev, school, reports   the queue's resume of the day's worker: bash
        <code_root>/deploy/aws/box/frankie_box_frankie_queue.sh with ACTION=resume RUN=<run> DAY=<day> CODE_ROOT=<code_root>
        (run and day from hub.json). The worker resumes the day from its own save point; the resume itself exits once it
        has handed the day back to the line (teacher-2, the second teacher turn, runs inside the day's class line, and
        reports is the class worker's day-reports step: the same resume). process_is_piece false: its exit is recorded;
        a non-zero exit is a 'doctor-error', not relaunched, because the revival failed rather than the piece dying again.
  forecaster   the spokes module's run_spoke(piece, hub_dir, day_sources(day, run)) as a standalone process (the doctor's
        own checkout, {box}); process_is_piece true.

CLI: python3 frankie_box_hub_doctor.py {watch,revive,status,unit} (--hub-dir, or --hub-root --run --day)
  watch   [--revivers FILE] [--launch auto|systemd-run|popen] [--state-dir D]   the doctor loop (what a unit runs); exits
          0 on SIGTERM/SIGINT ('doctor-stopped'), 1 when it cannot watch (recorded)
  revive  --piece P [--revivers FILE] [--launch ...]   one revive now ('doctor-revive-requested' by the CLI, then started)
  status  the probe: holder, waiters with liveness, pieces that have not written the current round, revives so far
  unit    prints a systemd unit for `watch` on this hub (nothing written)
Exit 0 on success, 1 on a failure (its message as JSON on stderr, and an event line), 2 on usage.
"""
import argparse
import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import frankie_box_hub as H  # noqa: E402 - the hub core, beside this file
import frankie_box_wake as W  # noqa: E402 - the box's stdlib-only event waker, beside this file

CODE_CURRENT = Path('/opt/frankie-box/code/current')
QUEUE_SH = 'deploy/aws/box/frankie_box_frankie_queue.sh'
DAY_PIECES = ('root', 'teacher', 'classroom', 'teacher-2', 'exchange', 'jev', 'school', 'reports')  # the queue resumes all
SPOKE_SNIPPET = ('import sys; sys.path.insert(0, sys.argv[1]); import frankie_box_hub_spokes as S; '
                 'piece, hub, run, day = sys.argv[2:6]; '
                 'S.run_spoke(piece, hub, S.day_sources(day, run or None))')


def _queue_resume_spec():
    return dict(argv=['/bin/bash', '{code_root}/' + QUEUE_SH],
                env=dict(ACTION='resume', RUN='{run}', DAY='{day}', CODE_ROOT='{code_root}'),
                process_is_piece=False,
                note='the queue resumes the day\'s worker from its own save (ACTION=resume RUN DAY on the newest '
                     'staged checkout); the worker takes the piece\'s turn again')


REVIVERS = {p: _queue_resume_spec() for p in DAY_PIECES}
REVIVERS['forecaster'] = dict(argv=['{python}', '-B', '-c', SPOKE_SNIPPET, '{box}', '{piece}', '{hub_dir}', '{run}',
                                    '{day}'],
                              env={}, process_is_piece=True,
                              note='the spokes module\'s run_spoke for this piece, standalone')


def register(piece, spec):
    """Add or replace the reviver of `piece` (spec None removes it)."""
    if spec is None:
        REVIVERS.pop(piece, None)
    else:
        REVIVERS[piece] = _check_spec(piece, spec)


def _check_spec(piece, spec):
    if not isinstance(spec, dict) or not isinstance(spec.get('argv'), list) or not spec['argv'] or \
            not all(isinstance(x, str) for x in spec['argv']):
        raise DoctorError('the reviver of %r needs "argv": a non-empty list of strings' % piece)
    env = spec.get('env') or {}
    if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise DoctorError('the reviver of %r: "env" must map strings to strings' % piece)
    return dict(spec, env=env, process_is_piece=bool(spec.get('process_is_piece')))


class DoctorError(Exception):
    pass


class _Stop(BaseException):
    """Raised by the SIGTERM/SIGINT handler out of the blocking wait."""


def _stop(signum, frame):
    raise _Stop(signal.Signals(signum).name)


def state_dir_of(hub_dir):
    hub_dir = Path(hub_dir)
    return hub_dir.parent / ('%s.doctor' % hub_dir.name)


def _code_root():
    real = Path(os.path.realpath(str(CODE_CURRENT)))
    for cand in (real, real / 'markets'):
        if (cand / QUEUE_SH).is_file():
            return str(cand)
    raise DoctorError('no staged checkout: %s resolves to %s and neither it nor %s/markets carries %s'
                      % (CODE_CURRENT, real, real, QUEUE_SH))


class _Context(dict):
    """The placeholders of a reviver command; code_root is resolved only when a spec names it."""

    def __missing__(self, key):
        if key == 'code_root':
            self['code_root'] = _code_root()
            return self['code_root']
        raise DoctorError('the reviver names an unknown placeholder {%s}' % key)


def load_revivers(path=None):
    table = {p: dict(s) for p, s in REVIVERS.items()}
    if path:
        try:
            extra = json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, ValueError) as error:
            raise DoctorError('the revivers file %s is unreadable: %s' % (path, error))
        if not isinstance(extra, dict):
            raise DoctorError('the revivers file %s must hold {piece: spec | null}' % path)
        for piece, spec in extra.items():
            if spec is None:
                table.pop(piece, None)
            else:
                table[piece] = _check_spec(piece, spec)
    return table


def _systemd_up():
    return shutil.which('systemd-run') is not None and os.path.isdir('/run/systemd/system')


# --------------------------------------------------------------------------------------------------------------- doctor

class Doctor:
    def __init__(self, hub_dir, revivers=None, launch='auto', state_dir=None, by=None):
        self.hub_dir = Path(hub_dir)
        self.revivers = revivers if revivers is not None else load_revivers()
        self.launch = launch
        self.state_dir = Path(state_dir) if state_dir else state_dir_of(self.hub_dir)
        self.by = by or 'doctor'
        self.handled = set()        # (piece, dead pid): each death acted on once
        self.pending = {}           # (piece, dead pid) -> facts, from takeover / waiter-gone lines not yet acted on
        self.counts = {}            # piece -> revives so far (from the event log, then live)
        self.children = {}          # pid -> {piece, proc, process_is_piece, count, log}
        self.offset = 0             # events.jsonl bytes already read
        self.waits = 0
        self.timed_waits = 0
        self.last_error = None

    # ---- events
    def ev(self, name, piece=None, **facts):
        return H.event(self.hub_dir, name, piece, by=self.by, **facts)

    def error(self, message, piece=None, **facts):
        try:
            self.ev('doctor-error', piece, message=message, **facts)
        except OSError as error:
            print(json.dumps(dict(error=message, event_log_error=str(error), piece=piece)), file=sys.stderr)

    # ---- the event log, read incrementally (complete lines only)
    def read_log(self):
        path = self.hub_dir / 'events.jsonl'
        try:
            with open(path, 'rb') as f:
                f.seek(self.offset)
                data = f.read()
        except FileNotFoundError:
            return
        end = data.rfind(b'\n')
        if end < 0:
            return
        self.offset += end + 1
        for raw in data[:end].split(b'\n'):
            try:
                line = json.loads(raw)
            except ValueError:
                continue
            self._note(line)

    def _note(self, line):
        name, piece = line.get('event'), line.get('piece')
        if name == 'doctor-revived':
            self.counts[piece] = max(self.counts.get(piece, 0), int(line.get('revive_count') or 0))
        elif name == 'doctor-revive-requested' and line.get('dead_pid') is not None:
            key = (piece, int(line['dead_pid']))
            self.handled.add(key)
            self.pending.pop(key, None)
        elif name in ('takeover', 'waiter-gone') and line.get('dead_pid') is not None and piece != H.CLEAN_PIECE:
            key = (piece, int(line['dead_pid']))
            if key not in self.handled:
                self.pending[key] = dict(cause=name, logged_utc=line.get('utc'), logged_by_pid=line.get('pid'))
        elif name in ('take', 'write') and piece is not None:
            # the piece took or wrote after a logged death: it is running again (revived by someone); not pending
            for key in [k for k in self.pending if k[0] == piece]:
                self.pending.pop(key)

    # ---- one look at the hub: act on deaths; return the live pids to watch
    def scan(self):
        self.read_log()
        hub_doc = H._hub(self.hub_dir)
        rnd = hub_doc.get('round')
        order = hub_doc.get('pieces') or []
        lock = H._read_lock(self.hub_dir)
        turn = H._turn(self.hub_dir)
        watch = []
        live = {}                   # piece -> live pids in the hub (holder or waiter)
        deaths = []
        if lock is not None:
            if H._live(lock.get('pid'), lock.get('pid_start')):
                watch.append(lock.get('pid'))
                live.setdefault(lock.get('piece'), set()).add(lock.get('pid'))
            else:
                deaths.append((lock.get('piece'), lock.get('pid'), 'holder-dead',
                               dict(held_since=lock.get('since_utc'))))
        for w in turn.get('waiters') or []:
            if H._live(w.get('pid'), w.get('pid_start')):
                watch.append(w.get('pid'))
                live.setdefault(w.get('piece'), set()).add(w.get('pid'))
            elif w.get('piece') in order:
                deaths.append((w.get('piece'), w.get('pid'), 'waiter-dead', dict(waiting_since=w.get('since_utc'))))
        for (piece, pid), facts in list(self.pending.items()):
            deaths.append((piece, pid, facts['cause'], facts))
        for pid, child in list(self.children.items()):
            code = child['proc'].poll() if child['proc'] is not None else (None if W.alive(pid) else 'unknown')
            if code is None:
                watch.append(pid)
                if child['process_is_piece']:
                    live.setdefault(child['piece'], set()).add(pid)
                continue
            del self.children[pid]
            self.ev('doctor-reviver-exited', child['piece'], reviver_pid=pid, exit_code=code,
                    revive_count=child['count'], process_is_piece=child['process_is_piece'], log=child['log'],
                    round_written=H._round_written(self.hub_dir, child['piece'], rnd))
            if child['process_is_piece']:
                if child['piece'] in order and not H._round_written(self.hub_dir, child['piece'], rnd):
                    deaths.append((child['piece'], pid, 'revived-process-exited', dict(exit_code=code)))
            elif code != 0:
                self.error('the reviver of %s exited %s: the revival failed (not relaunched; see its log)'
                           % (child['piece'], code), child['piece'], reviver_pid=pid, exit_code=code,
                           log=child['log'], log_tail=_tail(child['log']))
        for piece, pid, cause, facts in deaths:
            if pid is None:
                continue
            key = (piece, int(pid))
            if key in self.handled:
                continue
            self.handled.add(key)
            self.pending.pop(key, None)
            written = H._round_written(self.hub_dir, piece, rnd)
            others = sorted(p for p in live.get(piece, ()) if p != pid)
            if others:
                self.ev('doctor-no-revive', piece, dead_pid=pid, round=rnd, cause=cause,
                        reason='the piece is live again as pid %s' % others)
                continue
            if cause in ('waiter-dead', 'waiter-gone') and written:
                self.ev('doctor-no-revive', piece, dead_pid=pid, round=rnd, cause=cause,
                        reason='the waiter had written this round already')
                continue
            self.ev('doctor-revive-requested', piece, dead_pid=pid, round=rnd, cause=cause, round_written=written,
                    **{k: v for k, v in facts.items() if k != 'cause'})
            new = self.revive(piece, dead_pid=pid, hub_doc=hub_doc)
            if new is not None:
                watch.append(new)
        return [p for p in watch if p is not None]

    # ---- revive one piece
    def revive(self, piece, dead_pid=None, hub_doc=None):
        """Start `piece`'s reviver detached; record 'doctor-revived' (new pid, count). Returns the new pid or None
        (every None is an event: no reviver, or the failure)."""
        spec = self.revivers.get(piece)
        if spec is None:
            self.ev('doctor-no-reviver', piece, dead_pid=dead_pid, known=sorted(self.revivers),
                    reason='no reviver known for piece %s: it is not resumed; the pieces that need it keep waiting' % piece)
            return None
        try:
            hub_doc = hub_doc or H._hub(self.hub_dir)
            ctx = _Context(hub_dir=str(self.hub_dir), piece=piece, run=str(hub_doc.get('run') or ''),
                           day=str(hub_doc.get('day') or ''), round=str(hub_doc.get('round')),
                           python=sys.executable, box=str(HERE))
            argv = [a.format_map(ctx) for a in spec['argv']]
            env = {k: v.format_map(ctx) for k, v in (spec.get('env') or {}).items()}
        except (DoctorError, ValueError, IndexError, KeyError) as error:
            self.error('revive of %s not started: %s' % (piece, error), piece, dead_pid=dead_pid)
            return None
        count = self.counts.get(piece, 0) + 1
        env.update(HUB_DOCTOR_PIECE=piece, HUB_DOCTOR_REVIVE_COUNT=str(count),
                   HUB_DOCTOR_DEAD_PID='' if dead_pid is None else str(dead_pid), HUB_DOCTOR_HUB_DIR=str(self.hub_dir))
        try:
            (self.state_dir / 'logs').mkdir(parents=True, exist_ok=True)
            log = str(self.state_dir / 'logs' / ('%s-revive-%d.log' % (piece, count)))
            pid, proc, method, unit = self._start(piece, count, argv, env, log)
        except (OSError, subprocess.SubprocessError, DoctorError) as error:
            self.error('revive of %s not started: %s' % (piece, error), piece, dead_pid=dead_pid, argv=argv)
            return None
        self.counts[piece] = count
        self.children[pid] = dict(piece=piece, proc=proc, process_is_piece=spec['process_is_piece'], count=count,
                                  log=log)
        self.ev('doctor-revived', piece, new_pid=pid, revive_count=count, dead_pid=dead_pid, method=method, unit=unit,
                argv=argv, env={k: v for k, v in env.items()}, log=log, process_is_piece=spec['process_is_piece'],
                note=spec.get('note'))
        return pid

    def _start(self, piece, count, argv, env, log):
        launch = self.launch
        if launch == 'systemd-run' or (launch == 'auto' and _systemd_up()):
            unit = 'frankie-hub-revive-%s-%d-%d' % (piece, count, time.time_ns() // 1000)
            cmd = ['systemd-run', '--unit', unit, '--collect', '-p', 'StandardOutput=append:%s' % log,
                   '-p', 'StandardError=append:%s' % log] + \
                  [x for k, v in sorted(env.items()) for x in ('-E', '%s=%s' % (k, v))] + argv
            out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
            if out.returncode == 0:
                show = subprocess.run(['systemctl', 'show', '-p', 'MainPID', '--value', unit + '.service'],
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                try:
                    pid = int(show.stdout.decode().strip())
                except ValueError:
                    pid = 0
                if pid <= 0:
                    raise DoctorError('systemd-run started %s but its MainPID is unknown (%s)'
                                      % (unit, show.stdout.decode(errors='replace').strip()))
                return pid, None, 'systemd-run', unit
            text = out.stdout.decode(errors='replace').strip()[-400:]
            if launch == 'systemd-run':
                raise DoctorError('systemd-run exited %d: %s' % (out.returncode, text))
            self.ev('doctor-launch-fallback', piece, reason='systemd-run exited %d: %s; starting a new session instead'
                    % (out.returncode, text))
        with open(log, 'ab') as f:
            proc = subprocess.Popen(argv, env=dict(os.environ, **env), stdout=f, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
        return proc.pid, proc, 'popen-new-session', None

    # ---- the loop
    def _wait(self, waiter):
        self.waits += 1                                  # every wait is untimed: no argument, no interval
        waiter.wait()
        waiter.fired.clear()

    def watch(self):
        self.state_dir.mkdir(parents=True, exist_ok=True)
        lock = open(self.state_dir / 'doctor.lock', 'a+')
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            lock.seek(0)
            self.error('another doctor watches this hub (lock %s: %s)' % (self.state_dir / 'doctor.lock',
                                                                         lock.read().strip()))
            lock.close()
            return 1
        lock.seek(0)
        lock.truncate()
        lock.write('%d\n' % os.getpid())
        lock.flush()
        previous = {s: signal.signal(s, _stop) for s in (signal.SIGTERM, signal.SIGINT)}
        waiter = None
        try:
            waiter = W.Waiter([self.hub_dir, self.hub_dir / 'pieces'])
            if waiter.fd is None:
                self.error('no inotify on this host: the doctor will not fall back to a timed poll')
                return 1
            try:
                probe = W.pidfd(os.getpid())
                if probe is not None:
                    os.close(probe)
            except OSError as error:
                self.error('no pidfd on this host (%s): a dead holder could not wake the doctor' % error)
                return 1
            self.ev('doctor-started', None, doctor_pid=os.getpid(), revivers=sorted(self.revivers),
                    launch=self.launch, state_dir=str(self.state_dir))
            while True:
                try:
                    watch = self.scan()
                    self.last_error = None
                except _Stop:
                    raise
                except Exception as error:  # noqa: BLE001 - recorded, and the doctor keeps watching
                    text = '%s: %s' % (type(error).__name__, error)
                    if text != self.last_error:          # a doctor event wakes the doctor: record a repeat once
                        self.error('scan failed: %s' % text)
                        self.last_error = text
                    watch = []
                for pid in watch:
                    if pid not in waiter.pids and W.alive(pid):
                        waiter.watch_pid(pid)
                self._wait(waiter)
        except _Stop as stop:
            self.ev('doctor-stopped', None, signal=str(stop), waits=self.waits, timed_waits=self.timed_waits,
                    revives=dict(self.counts), children_left=sorted(self.children))
            return 0
        finally:
            if waiter is not None:
                waiter.close()
            for s, h in previous.items():
                signal.signal(s, h)
            lock.close()


def _tail(path, n=2000):
    try:
        with open(path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - n))
            return f.read().decode('utf-8', 'replace')
    except OSError:
        return None


# --------------------------------------------------------------------------------------------------------- module API

def watch(hub_dir, revivers=None, launch='auto', state_dir=None):
    """The event-driven doctor loop on one hub. Never times out; returns 0 on SIGTERM/SIGINT, 1 when it cannot watch."""
    return Doctor(hub_dir, revivers, launch, state_dir).watch()


def revive(hub_dir, piece, revivers=None, launch='auto', state_dir=None, by='cli'):
    """One revive of `piece` now (recorded as requested by `by`). Returns the new pid or None (recorded)."""
    d = Doctor(hub_dir, revivers, launch, state_dir, by=by)
    d.read_log()
    hub_doc = H._hub(hub_dir)
    d.ev('doctor-revive-requested', piece, dead_pid=None, round=hub_doc.get('round'), cause='requested by ' + by,
         round_written=H._round_written(hub_dir, piece, hub_doc.get('round')))
    return d.revive(piece, hub_doc=hub_doc)


def status(hub_dir, state_dir=None):
    """The probe: holder, waiters with liveness, pieces that have not written the current round, revives so far."""
    hub_dir = Path(hub_dir)
    doc = H._hub(hub_dir)
    rnd, order = doc.get('round'), doc.get('pieces') or []
    lock, turn = H._read_lock(hub_dir), H._turn(hub_dir)
    revives, last, no_reviver, errors, requested = {}, [], [], [], []
    try:
        with open(hub_dir / 'events.jsonl', 'rb') as f:
            for raw in f:
                if b'"doctor-' not in raw:
                    continue
                try:
                    line = json.loads(raw)
                except ValueError:
                    continue
                name = line.get('event')
                if name == 'doctor-revived':
                    revives[line.get('piece')] = line.get('revive_count')
                    last.append({k: line.get(k) for k in ('utc', 'piece', 'new_pid', 'dead_pid', 'revive_count',
                                                          'method')})
                elif name == 'doctor-revive-requested':
                    requested.append({k: line.get(k) for k in ('utc', 'piece', 'dead_pid', 'cause', 'round')})
                elif name == 'doctor-no-reviver':
                    no_reviver.append({k: line.get(k) for k in ('utc', 'piece', 'dead_pid')})
                elif name == 'doctor-error':
                    errors.append({k: line.get(k) for k in ('utc', 'piece', 'message')})
    except FileNotFoundError:
        pass
    sd = Path(state_dir) if state_dir else state_dir_of(hub_dir)
    running = None
    try:
        with open(sd / 'doctor.lock', 'r') as f:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
                running = False
            except OSError:
                running = dict(pid=(f.read().strip() or None))
    except FileNotFoundError:
        running = False
    return dict(hub_dir=str(hub_dir), run=doc.get('run'), day=doc.get('day'), round=rnd, done=doc.get('done'),
                holder=(lock or {}).get('piece'), holder_pid=(lock or {}).get('pid'),
                holder_alive=None if lock is None else H._live(lock.get('pid'), lock.get('pid_start')),
                waiters=[dict(piece=w.get('piece'), pid=w.get('pid'), since_utc=w.get('since_utc'),
                              alive=H._live(w.get('pid'), w.get('pid_start')), ordered=w.get('ordered'),
                              written=H._round_written(hub_dir, w.get('piece'), rnd))
                         for w in turn.get('waiters') or []],
                not_written=[p for p in order if not H._round_written(hub_dir, p, rnd)],
                revives=revives, last_revives=last[-10:], revive_requests=len(requested), last_requests=requested[-10:],
                no_reviver=no_reviver[-10:], errors=len(errors), last_errors=errors[-5:], doctor_running=running)


def unit_text(hub_dir, revivers=None):
    exe = '%s -B %s watch --hub-dir %s' % (sys.executable, Path(__file__).resolve(), hub_dir)
    if revivers:
        exe += ' --revivers %s' % revivers
    return '\n'.join([
        '[Unit]', 'Description=Frankie hub doctor for %s' % hub_dir, '',
        '[Service]', 'Type=simple', 'ExecStart=%s' % exe, 'KillSignal=SIGTERM', 'Restart=on-failure', '',
        '[Install]', 'WantedBy=multi-user.target', ''])


# ------------------------------------------------------------------------------------------------------------------ CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description='The hub doctor (frankie_box_hub_doctor.py).')
    ap.add_argument('command', choices=['watch', 'revive', 'status', 'unit'])
    ap.add_argument('--hub-dir')
    ap.add_argument('--hub-root')
    ap.add_argument('--run')
    ap.add_argument('--day')
    ap.add_argument('--piece')
    ap.add_argument('--revivers', help='JSON file {piece: {argv, env, process_is_piece, note} | null}')
    ap.add_argument('--launch', choices=['auto', 'systemd-run', 'popen'], default='auto')
    ap.add_argument('--state-dir')
    a = ap.parse_args(argv)
    if a.hub_dir:
        hub_dir = Path(a.hub_dir)
    elif a.hub_root and a.run and a.day:
        hub_dir = H.hub_dir_of(a.hub_root, a.run, a.day)
    else:
        print(json.dumps(dict(error='give --hub-dir, or --hub-root --run --day')), file=sys.stderr)
        return 2
    try:
        if a.command == 'unit':
            print(unit_text(hub_dir, a.revivers))
            return 0
        if a.command == 'status':
            print(json.dumps(status(hub_dir, a.state_dir), indent=1, default=str))
            return 0
        revivers = load_revivers(a.revivers)
        if a.command == 'watch':
            return Doctor(hub_dir, revivers, a.launch, a.state_dir).watch()
        if not a.piece:
            print(json.dumps(dict(error='revive needs --piece')), file=sys.stderr)
            return 2
        pid = revive(hub_dir, a.piece, revivers, a.launch, a.state_dir)
        print(json.dumps(dict(piece=a.piece, new_pid=pid)))
        return 0 if pid is not None else 1
    except (DoctorError, H.HubError) as error:
        try:
            H.event(hub_dir, 'doctor-error', a.piece, message=str(error), command=a.command)
        except OSError:
            pass
        print(json.dumps(dict(error=str(error))), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
