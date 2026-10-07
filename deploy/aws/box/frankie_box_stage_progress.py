"""Stage heartbeats: one shared probe contract for every stage child of the experiment (Greg, 2026-10-07: probes on
EVERY step, so a running day shows its output speed, size and heartbeats; CLAUDE.md "ALWAYS HAVE PROBES ATTACHED").

Contract (FRANKIE_STAGE_HEARTBEAT_V1): Run.child (and the one-day reporter) attaches a Heartbeat to every stage child
it starts. The orchestrator side appends one JSON line about every INTERVAL seconds to
<run>/days/<day>/progress/<stage>.jsonl (a key without a day, e.g. a batch: <run>/batches/<key>/progress/<stage>.jsonl):

  schema, stage, key, pid, utc, at, elapsed_s, interval_s, phase, units_done, unit, units_total, bytes_out, files_out,
  bytes_out_per_min, units_per_min, rss_bytes, processes, log_bytes, sources, final (False on a heartbeat)

and one final line (final True) with outcome and exit_code when the child ends. Everything is measured from outside the
child (Linux /proc of the child's process tree, its log file) or read from what the child itself already publishes:
  - units / phase: the child's own phase file (report_phase below, env FRANKIE_STAGE_PROGRESS) when it writes one, else
    an existing FRANKIE_WORK_PROBE_V1 progress.json (frankie_box_progress.Probe: the ROOT/boss_session, the classroom
    publication) of a process in the tree: first in the directories the caller names (probe_dirs: the ROOT's own
    attempt directory, experiment-roots/<attempt>, and its immediate subdirectories such as native-overlap/), then
    beside the files the tree holds open, else the last log line as phase text and units unknown (None, never zero);
  - work_probes (FA-4): every live work probe found in the named directories, each with its own stage, completed, total
    and completed_per_min (the ROOT's legacy pass and its forked native pass side by side);
  - stall (L-2 watch): units_unchanged_s = seconds the units have not moved while the heartbeat keeps writing, and
    stalled True once that reaches STALL_SECONDS (a hung pool or worker shows here; a probe never stops the stage);
  - bytes_out: /proc/<pid>/io write_bytes summed over every process of the tree ever sampled (the largest value seen per
    process; a child that lived and exited between two samples is not seen: a LOWER BOUND, labelled);
  - files_out: distinct regular files the tree was seen holding open for writing at the samples (a lower bound);
  - rss_bytes: VmRSS summed over the tree's live processes at the sample.
It never changes a child's inputs, outputs, environment beyond FRANKIE_STAGE_PROGRESS, scheduling or exit; a sampling
failure is written on the line (`sample_error`) and never raised. Not knowledge, not evidence, not a gate.

Read: frankie_box_progress.py --run-dir <run> --day <day> (frankie_box_progress.sh RUN_DIR=... DAY=...), read-only,
on the box-progress lock: per stage the last heartbeat's age, rate, units, bytes and rss, STALE when the last line is
older than 3 intervals while not final.
"""
import json
import os
from pathlib import Path
import re
import threading
import time

SCHEMA = 'FRANKIE_STAGE_HEARTBEAT_V1'
PHASE_SCHEMA = 'FRANKIE_STAGE_PHASE_V1'
INTERVAL = 30                      # seconds between heartbeat lines (the contract asks 30-60 s)
STALE_INTERVALS = 3                # the probe flags a running stage whose last line is older than this many intervals
STALL_SECONDS = 600                # the probe flags a running stage whose units have not moved for this long (L-2 watch)
ENV = 'FRANKIE_STAGE_PROGRESS'     # the child's own phase file (report_phase), set by Run.child
WORK_PROBE = 'FRANKIE_WORK_PROBE_V1'
LOG_TAIL = 4096                    # bytes read from the end of the log for the last line (phase text fallback)


def progress_dir(run_dir, key):
    """<run>/days/<day>/progress for a day key (YYYYMMDD first, or a key naming one day: day-YYYYMMDD,
    YYYYMMDD-successor-...), else <run>/batches/<key>/progress."""
    key = str(key)
    match = re.match(r'^(?:day-)?([0-9]{8})(?:$|[^0-9])', key)
    if match:
        return Path(run_dir) / 'days' / match.group(1) / 'progress'
    return Path(run_dir) / 'batches' / re.sub(r'[^A-Za-z0-9_.-]', '_', key) / 'progress'


def progress_path(run_dir, key, stage):
    return progress_dir(run_dir, key) / ('%s.jsonl' % stage)


_LAST_WRITE = [0.0]


def report_phase(phase, units_done=None, units_total=None, unit=None, every=None, **extra):
    """Child side, optional: the stage's own phase and units, written atomically to $FRANKIE_STAGE_PROGRESS (the parent's
    heartbeat reads it on its next line). A no-op outside a Run.child stage; never raises (a probe is never the stage's
    outcome). Call it at phase boundaries, never per record. every=N (seconds): inside a loop, skip the write when the
    last one is younger than N s, except the last unit (units_done == units_total)."""
    path = os.environ.get(ENV)
    if not path:
        return
    now = time.monotonic()
    if every and now - _LAST_WRITE[0] < every and not (units_total is not None and units_done == units_total):
        return
    _LAST_WRITE[0] = now
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        body = dict(schema=PHASE_SCHEMA, pid=os.getpid(), at=time.time(), phase=str(phase)[:200],
                    units_done=units_done, units_total=units_total, unit=unit, **extra)
        pending = target.with_name(target.name + '.%d.pending' % os.getpid())
        pending.write_text(json.dumps(body, sort_keys=True, default=str) + '\n', encoding='utf-8')
        os.replace(pending, target)
    except Exception:  # noqa: BLE001 - the probe never changes the stage's outcome
        pass


def _read(path):
    try:
        return Path(path).read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None


def _ppid_map():
    """{pid: (ppid, start ticks)} of every process readable in /proc."""
    out = {}
    try:
        names = os.listdir('/proc')
    except OSError:
        return out
    for name in names:
        if not name.isdigit():
            continue
        text = _read('/proc/%s/stat' % name)
        if not text:
            continue
        try:
            fields = text.rsplit(')', 1)[1].split()
            out[int(name)] = (int(fields[1]), int(fields[19]), fields[0])
        except (IndexError, ValueError):
            continue
    return out


def _tree(root):
    """The live process tree under root (root included): [(pid, start ticks)]."""
    table = _ppid_map()
    if root not in table:
        return []
    children = {}
    for pid, (ppid, _, _) in table.items():
        children.setdefault(ppid, []).append(pid)
    out, stack = [], [root]
    while stack:
        pid = stack.pop()
        state = table.get(pid)
        if state is None or state[2] in ('Z', 'X'):
            continue
        out.append((pid, state[1]))
        stack.extend(children.get(pid, ()))
    return out


def _field(text, name):
    for line in (text or '').splitlines():
        if line.startswith(name):
            try:
                return int(line.split()[1])
            except (IndexError, ValueError):
                return None
    return None


class Heartbeat:
    """The orchestrator-side heartbeat of ONE stage child (see the module contract). start(pid) after the child is
    started; stop(outcome, exit_code) after it ends (writes the final line). Never raises out of either."""

    def __init__(self, run_dir, key, stage, log_path=None, interval=INTERVAL, probe_dirs=()):
        self.path = progress_path(run_dir, key, stage)
        self.phase_file = self.path.with_name('%s.phase.json' % stage)
        self.stage, self.key, self.log_path, self.interval = stage, str(key), log_path, interval
        self.pid, self.started = None, None
        self.peak_write = {}            # (pid, start ticks) -> the largest write_bytes seen
        self.written_files = set()
        self.probe_dirs = {}            # directory -> last checked (FRANKIE_WORK_PROBE_V1 progress.json beside open files)
        self.named_dirs = [str(d) for d in (probe_dirs or ()) if d]   # the caller's known probe directories, checked first
        self.probe_previous = {}        # probe directory -> (monotonic, completed) for each work probe's own rate
        self.units_moved = None         # (monotonic, units_done) when the units last changed (the stall watch)
        self.previous = None            # (monotonic, bytes_out, units_done) of the last line, for the rates
        self.stop_event = threading.Event()
        self.thread = None
        self.error = None

    def env(self):
        """The one variable the child receives: where its optional phase file goes."""
        return {ENV: str(self.phase_file)}

    def start(self, pid):
        try:
            self.pid, self.started = pid, time.monotonic()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                self.phase_file.unlink()          # a previous attempt's phase is not this child's
            except OSError:
                pass
            self.thread = threading.Thread(target=self._loop, name='heartbeat-%s-%s' % (self.stage, self.key), daemon=True)
            self.thread.start()
        except Exception as error:  # noqa: BLE001 - the probe never changes the stage
            self.error = '%s: %s' % (type(error).__name__, error)

    def _loop(self):
        self._write(self.sample())
        while not self.stop_event.wait(self.interval):
            self._write(self.sample())

    def stop(self, outcome, exit_code=None):
        try:
            self.stop_event.set()
            if self.thread is not None:
                self.thread.join(timeout=10)
            line = self.sample(final=True)
            line.update(outcome=outcome, exit_code=exit_code)
            self._write(line)
        except Exception:  # noqa: BLE001
            pass

    def _write(self, line):
        try:
            with open(self.path, 'a', encoding='utf-8') as handle:
                handle.write(json.dumps(line, sort_keys=True, default=str) + '\n')
        except OSError:
            pass

    def _named_probes(self, pids, mono):
        """The live work probes in the named directories and their immediate subdirectories (FA-4: the ROOT writes its
        FRANKIE_WORK_PROBE_V1 progress.json at experiment-roots/<attempt>/, the forked native pass at
        <attempt>/native-overlap/; neither is beside a file the tree holds open). Each with its own completed_per_min."""
        live, found = {pid for pid, _ in pids}, []
        for named in self.named_dirs:
            candidates = [Path(named)]
            try:
                candidates += sorted(p for p in Path(named).iterdir() if p.is_dir() and not p.is_symlink())
            except OSError:
                pass
            for directory in candidates:
                text = _read(directory / 'progress.json')
                if not text:
                    continue
                try:
                    value = json.loads(text)
                except ValueError:
                    continue
                if not (isinstance(value, dict) and value.get('schema') == WORK_PROBE and value.get('pid') in live):
                    continue
                item = dict(dir=str(directory), stage=value.get('stage'), completed=value.get('completed'),
                            total=value.get('total'), state=value.get('state'), probe_at=value.get('at'),
                            reader_workers=value.get('reader_workers'))
                done, before = value.get('completed'), self.probe_previous.get(str(directory))
                if isinstance(done, int) and before is not None and before[2] == value.get('stage') \
                        and mono - before[0] > 0:
                    item['completed_per_min'] = round((done - before[1]) / ((mono - before[0]) / 60.0), 3)
                if isinstance(done, int):
                    self.probe_previous[str(directory)] = (mono, done, value.get('stage'))
                found.append(item)
        return found

    def _units_from_probe(self, pids):
        """An existing FRANKIE_WORK_PROBE_V1 progress.json of a process in the tree (its stage, completed, total)."""
        live = {pid for pid, _ in pids}
        for directory in self.named_dirs + [d for d in self.probe_dirs if d not in self.named_dirs]:
            text = _read(Path(directory) / 'progress.json')
            if not text:
                continue
            try:
                value = json.loads(text)
            except ValueError:
                continue
            if isinstance(value, dict) and value.get('schema') == WORK_PROBE and value.get('pid') in live:
                return dict(phase=value.get('stage'), units_done=value.get('completed'), units_total=value.get('total'),
                            unit='%s items' % value.get('stage'), source='work probe %s' % directory)
        return None

    def sample(self, final=False):
        now, mono = time.time(), time.monotonic()
        line = dict(schema=SCHEMA, stage=self.stage, key=self.key, pid=self.pid, at=round(now, 3),
                    utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now)),
                    elapsed_s=round(mono - self.started, 1) if self.started is not None else None,
                    interval_s=self.interval, final=final, sources={})
        try:
            pids = _tree(self.pid) if self.pid else []
            self._pids = pids
            rss = 0
            for pid, ticks in pids:
                rss += (_field(_read('/proc/%d/status' % pid), 'VmRSS:') or 0) * 1024
                written = _field(_read('/proc/%d/io' % pid), 'write_bytes:')
                if written is not None:
                    key = (pid, ticks)
                    self.peak_write[key] = max(self.peak_write.get(key, 0), written)
                fd_dir = '/proc/%d/fd' % pid
                try:
                    fds = os.listdir(fd_dir)
                except OSError:
                    fds = []
                for fd in fds:
                    try:
                        target = os.readlink('%s/%s' % (fd_dir, fd))
                    except OSError:
                        continue
                    if not target.startswith('/') or target.startswith(('/dev/', '/proc/', '/sys/')):
                        continue
                    flags = _field(_read('/proc/%d/fdinfo/%s' % (pid, fd)), 'flags:')
                    if flags is not None:
                        # fdinfo flags are octal text; O_ACCMODE 1 = write only, 2 = read/write
                        try:
                            mode = int(str(flags), 8) & 3
                        except ValueError:
                            mode = 0
                        if mode in (1, 2) and target != str(self.log_path):
                            self.written_files.add(target)
                    parent = os.path.dirname(target)
                    for directory in (parent, os.path.dirname(parent), os.path.dirname(os.path.dirname(parent))):
                        if directory and directory not in self.probe_dirs and len(self.probe_dirs) < 64:
                            self.probe_dirs[directory] = now
            line.update(processes=len(pids), rss_bytes=rss if pids else None,
                        bytes_out=sum(self.peak_write.values()) if self.peak_write else None,
                        files_out=len(self.written_files))
            line['sources'].update(bytes_out='/proc io write_bytes of the sampled tree (lower bound)',
                                   files_out='regular files seen open for writing at the samples (lower bound)')
        except Exception as error:  # noqa: BLE001 - a failed sample is written, never raised
            line['sample_error'] = '%s: %s' % (type(error).__name__, error)
        units = None
        try:
            text = _read(self.phase_file)
            value = json.loads(text) if text else None
            if isinstance(value, dict) and value.get('schema') == PHASE_SCHEMA:
                units = dict(phase=value.get('phase'), units_done=value.get('units_done'),
                             units_total=value.get('units_total'), unit=value.get('unit'), source='stage phase file')
        except ValueError:
            units = None
        if self.named_dirs:
            try:
                line['work_probes'] = self._named_probes(getattr(self, '_pids', None) or [], mono)
            except Exception as error:  # noqa: BLE001 - a failed sample is written, never raised
                line['work_probes_error'] = '%s: %s' % (type(error).__name__, error)
        if units is None:
            units = self._units_from_probe(getattr(self, '_pids', None) or [])
        if self.log_path:
            try:
                size = os.path.getsize(self.log_path)
                line['log_bytes'] = size
                if units is None:
                    with open(self.log_path, 'rb') as handle:
                        handle.seek(max(0, size - LOG_TAIL))
                        tail = [x for x in handle.read().decode('utf-8', 'replace').splitlines() if x.strip()]
                    units = dict(phase=(tail[-1][:160] if tail else None), units_done=None, units_total=None, unit=None,
                                 source='the last log line (the stage publishes no units)')
            except OSError:
                pass
        units = units or dict(phase=None, units_done=None, units_total=None, unit=None, source='nothing published')
        line.update(phase=units.get('phase'), units_done=units.get('units_done'), units_total=units.get('units_total'),
                    unit=units.get('unit'))
        line['sources']['units'] = units.get('source')
        if self.previous is not None:
            span = (mono - self.previous[0]) / 60.0
            if span > 0:
                if line.get('bytes_out') is not None and self.previous[1] is not None:
                    line['bytes_out_per_min'] = round((line['bytes_out'] - self.previous[1]) / span, 1)
                if isinstance(line.get('units_done'), (int, float)) and isinstance(self.previous[2], (int, float)):
                    line['units_per_min'] = round((line['units_done'] - self.previous[2]) / span, 3)
        self.previous = (mono, line.get('bytes_out'), line.get('units_done'))
        # the stall watch (L-2): units that do not move while this heartbeat keeps writing; None while units are unknown
        done = line.get('units_done')
        if isinstance(done, (int, float)):
            marker = (line.get('phase'), done)
            if self.units_moved is None or self.units_moved[1] != marker:
                self.units_moved = (mono, marker)
            line['units_unchanged_s'] = round(mono - self.units_moved[0], 1)
            line['stalled'] = (not final) and line['units_unchanged_s'] >= STALL_SECONDS
        return line


def last_line(path, limit=65536):
    """The last JSON line of a jsonl file (read from its end only), or None."""
    try:
        with open(path, 'rb') as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - limit))
            lines = [x for x in handle.read().decode('utf-8', 'replace').splitlines() if x.strip()]
        for text in reversed(lines):
            try:
                return json.loads(text)
            except ValueError:
                continue
    except OSError:
        return None
    return None


def stages_summary(run_dir, day=None):
    """Read-only: per stage of the day (or every day and batch) the last heartbeat line with its age; STALE when a
    running stage's last line is older than STALE_INTERVALS intervals."""
    run_dir = Path(run_dir)
    dirs = ([progress_dir(run_dir, day)] if day else
            sorted(run_dir.glob('days/*/progress')) + sorted(run_dir.glob('batches/*/progress')))
    out, now = [], time.time()
    for directory in dirs:
        for path in sorted(directory.glob('*.jsonl')):
            line = last_line(path)
            if not isinstance(line, dict):
                out.append(dict(file=str(path), status='unreadable'))
                continue
            age = round(now - float(line.get('at') or 0), 1)
            interval = line.get('interval_s') or INTERVAL
            status = ('final: %s' % line.get('outcome') if line.get('final') else
                      'STALE' if age > STALE_INTERVALS * interval else
                      'STALLED' if line.get('stalled') else 'running')
            out.append(dict(stage=line.get('stage'), key=line.get('key'), status=status, age_s=age, pid=line.get('pid'),
                            elapsed_s=line.get('elapsed_s'), phase=line.get('phase'), units_done=line.get('units_done'),
                            units_total=line.get('units_total'), unit=line.get('unit'),
                            units_per_min=line.get('units_per_min'), bytes_out=line.get('bytes_out'),
                            bytes_out_per_min=line.get('bytes_out_per_min'), files_out=line.get('files_out'),
                            rss_bytes=line.get('rss_bytes'), processes=line.get('processes'),
                            exit_code=line.get('exit_code'), units_unchanged_s=line.get('units_unchanged_s'),
                            stalled=line.get('stalled'), work_probes=line.get('work_probes'), file=str(path)))
    return dict(schema=SCHEMA + '_SUMMARY', run_dir=str(run_dir), day=day, at=now, stale_after_intervals=STALE_INTERVALS,
                stalled_after_seconds=STALL_SECONDS, stages=out)
