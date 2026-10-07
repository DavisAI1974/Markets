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

Stacks pass (2026-10-07 night, session 5; additive, every earlier field and line kept): the work probes are found for
EVERY stage, not only where the caller names a directory: besides probe_dirs and the open-file directories, the
heartbeat looks in every absolute directory the child's environment or command line names (OUTPUT_ROOT, OUT_DIR,
CLASSROOM, TEACHER_ROWS, --out-dir ..., a file's own directory) and in each process's working directory, and in their
immediate subdirectories (native-overlap/, <line>-worker/); work_probes is on every line (an empty list = none found).
Each work probe carries its own completed_per_min, units_unchanged_s, stalled (report-only, STALL_SECONDS) and the
CPU ranges of its writer (cpu_ranges: the writer's Cpus_allowed_list, or the probe's own cpus/cpu_ranges field when it
records one); the line carries the stage tree root's cpu_ranges. A FRANKIE_WORK_PROBE_V1 file written by any writer is
accepted (the frankie_box_progress.Probe fields, plus optional units / unit / cpus / cpu_ranges / workers); missing
fields read as None, never zero. run_probes(run_dir) reads the probes outside any stage child: the Run's own
<run>/progress.json and the queue line workers (frankie-queue/<line>-worker/progress.json) with the kick receipt's
run_settings (FA-6).

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
try:
    CLOCK_TICKS = os.sysconf('SC_CLK_TCK')
except (AttributeError, ValueError, OSError):
    CLOCK_TICKS = 100
WORK_ROOT = '/opt/frankie-box/work/'   # where a process-named directory may hold a work probe (stacks pass)
MAX_PROBE_DIRS = 256               # directories checked per sample (one small read each)
QUEUE_DIR = Path('/opt/frankie-box/work/frankie-queue')


def cpu_list_of(pid):
    """The process's Cpus_allowed_list ('0-31', '8-15,24-31'), or None."""
    for line in (_read('/proc/%d/status' % pid) or '').splitlines():
        if line.startswith('Cpus_allowed_list:'):
            return line.split(':', 1)[1].strip() or None
    return None


def _ranges(cpus):
    runs = []
    for cpu in sorted(set(int(c) for c in cpus)):
        if runs and cpu == runs[-1][1] + 1:
            runs[-1][1] = cpu
        else:
            runs.append([cpu, cpu])
    return ','.join(str(a) if a == b else '%d-%d' % (a, b) for a, b in runs)


def probe_item(value, directory):
    """One FRANKIE_WORK_PROBE_V1 file as a work-probe item, whichever writer wrote it: the Probe fields, plus any of
    units / unit / workers / cpus / cpu_ranges a writer records; cpu_ranges falls back to the writer's
    Cpus_allowed_list. Missing fields are None, never zero."""
    item = dict(dir=str(directory), stage=value.get('stage'), completed=value.get('completed'),
                total=value.get('total'), state=value.get('state'), probe_at=value.get('at'),
                reader_workers=value.get('reader_workers'), pid=value.get('pid'), failed=value.get('failed'),
                in_flight=value.get('in_flight'), unit=value.get('unit'), workers=value.get('workers'))
    ranges = value.get('cpu_ranges')
    if ranges is None and isinstance(value.get('cpus'), list):
        try:
            ranges = _ranges(value['cpus'])
        except (TypeError, ValueError):
            ranges = None
    if ranges is None and isinstance(value.get('pid'), int):
        ranges = cpu_list_of(value['pid'])
    item['cpu_ranges'] = ranges
    return item


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
        self.peak_cpu = {}              # (pid, start ticks) -> the largest utime+stime ticks seen (CPU use, stacks pass)
        self.written_files = set()
        self.probe_dirs = {}            # directory -> last checked (FRANKIE_WORK_PROBE_V1 progress.json beside open files)
        self.named_dirs = [str(d) for d in (probe_dirs or ()) if d]   # the caller's known probe directories, checked first
        self.probe_previous = {}        # probe directory -> (monotonic, completed) for each work probe's own rate
        self.units_moved = None         # (monotonic, units_done) when the units last changed (the stall watch)
        self.probe_moved = {}           # probe directory -> (monotonic, (stage, completed)) when that probe last moved
        self.seen_processes = {}        # (pid, start ticks) -> [absolute directories its environ/argv/cwd name]
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

    def _process_dirs(self, pids):
        """Absolute directories each process of the tree names (stacks pass, read once per process): every environment
        value and command-line argument that is an absolute path (a directory itself, or a file's own directory), and
        its working directory. Under /opt/frankie-box/work only (never the code checkout, venv or system paths)."""
        out = []
        for pid, ticks in pids:
            key = (pid, ticks)
            if key not in self.seen_processes:
                names = []
                try:
                    with open('/proc/%d/environ' % pid, 'rb') as handle:
                        names += [x.split(b'=', 1)[1] for x in handle.read().split(b'\0') if b'=' in x]
                except OSError:
                    pass
                try:
                    with open('/proc/%d/cmdline' % pid, 'rb') as handle:
                        names += handle.read().split(b'\0')
                except OSError:
                    pass
                found = []
                try:
                    found.append(os.readlink('/proc/%d/cwd' % pid))
                except OSError:
                    pass
                for raw in names:
                    for part in raw.decode('utf-8', 'replace').split(','):
                        if part.startswith(WORK_ROOT):
                            found.append(part if os.path.isdir(part) else os.path.dirname(part))
                self.seen_processes[key] = [d for d in dict.fromkeys(found)
                                            if d.startswith(WORK_ROOT) and d.rstrip('/') != WORK_ROOT.rstrip('/')]
            out += self.seen_processes[key]
        return out

    def _candidates(self, pids):
        """Every directory a work probe of this stage may be in, in a fixed order: the caller's named directories, the
        directories the tree's environment / command lines / working directories name, the open-file directories; each
        followed by its immediate subdirectories (named and named-by-process only). At most MAX_PROBE_DIRS."""
        out = []
        for base in self.named_dirs + self._process_dirs(pids):
            out.append(Path(base))
            try:
                out += sorted(p for p in Path(base).iterdir() if p.is_dir() and not p.is_symlink())
            except OSError:
                pass
        out += [Path(d) for d in self.probe_dirs]
        return list(dict.fromkeys(out))[:MAX_PROBE_DIRS]

    def _named_probes(self, pids, mono):
        """The live work probes of the stage (FA-4 for every stage: the ROOT writes its FRANKIE_WORK_PROBE_V1
        progress.json at experiment-roots/<attempt>/, the forked native pass at <attempt>/native-overlap/; the other
        pieces wherever their process names a directory, see _candidates). Each with its own completed_per_min,
        units_unchanged_s, stalled and cpu_ranges."""
        live, found = {pid for pid, _ in pids}, []
        for directory in self._candidates(pids):
            text = _read(directory / 'progress.json')
            if not text:
                continue
            try:
                value = json.loads(text)
            except ValueError:
                continue
            if not (isinstance(value, dict) and value.get('schema') == WORK_PROBE and value.get('pid') in live):
                continue
            item = probe_item(value, directory)
            done, before = value.get('completed'), self.probe_previous.get(str(directory))
            if isinstance(done, int) and before is not None and before[2] == value.get('stage') \
                    and mono - before[0] > 0:
                item['completed_per_min'] = round((done - before[1]) / ((mono - before[0]) / 60.0), 3)
            if isinstance(done, int):
                self.probe_previous[str(directory)] = (mono, done, value.get('stage'))
                marker = (value.get('stage'), done)
                moved = self.probe_moved.get(str(directory))
                if moved is None or moved[1] != marker:
                    self.probe_moved[str(directory)] = moved = (mono, marker)
                item['units_unchanged_s'] = round(mono - moved[0], 1)
                item['stalled'] = item['units_unchanged_s'] >= STALL_SECONDS and value.get('state') == 'running'
            found.append(item)
        return found

    def _units_from_probe(self, pids):
        """An existing FRANKIE_WORK_PROBE_V1 progress.json of a process in the tree (its stage, completed, total)."""
        live = {pid for pid, _ in pids}
        for directory in self._candidates(pids):
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
                stat = _read('/proc/%d/stat' % pid)
                try:
                    fields = stat.rsplit(')', 1)[1].split() if stat else None
                    if fields:
                        self.peak_cpu[(pid, ticks)] = max(self.peak_cpu.get((pid, ticks), 0),
                                                          int(fields[11]) + int(fields[12]))
                except (IndexError, ValueError):
                    pass
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
            # CPU use (stacks pass, additive): utime+stime of every process of the tree ever sampled, in seconds (a
            # LOWER BOUND like bytes_out); cpus_busy = CPU-seconds per wall second since the last line
            line['cpu_seconds'] = round(sum(self.peak_cpu.values()) / float(CLOCK_TICKS), 2) if self.peak_cpu else None
            line['sources']['cpu_seconds'] = '/proc stat utime+stime of the sampled tree (lower bound)'
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
        try:                            # every stage (stacks pass): an empty list = no live work probe found
            line['work_probes'] = self._named_probes(getattr(self, '_pids', None) or [], mono)
        except Exception as error:  # noqa: BLE001 - a failed sample is written, never raised
            line['work_probes_error'] = '%s: %s' % (type(error).__name__, error)
        if self.pid:
            line['cpu_ranges'] = cpu_list_of(self.pid) or getattr(self, 'last_cpu_ranges', None)
            self.last_cpu_ranges = line['cpu_ranges']
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
        if (units is None or units.get('units_done') is None) and getattr(self, 'last_units', None):
            # stacks pass: once the tree has exited (the final line) or between two writes, the last measured units are
            # carried, labelled, instead of None
            units = dict(self.last_units, source='the last measured units (%s), carried' % self.last_units.get('source'))
        elif units is not None and units.get('units_done') is not None:
            self.last_units = dict(units)
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
            if line.get('cpu_seconds') is not None and getattr(self, '_cpu_previous', None) is not None:
                line['cpus_busy'] = round((line['cpu_seconds'] - self._cpu_previous) / (span * 60.0), 2) if span > 0 else None
        self._cpu_previous = line.get('cpu_seconds')
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
                            stalled=line.get('stalled'), work_probes=line.get('work_probes'), file=str(path),
                            units_source=(line.get('sources') or {}).get('units'), cpu_ranges=line.get('cpu_ranges'),
                            cpu_seconds=line.get('cpu_seconds'), cpus_busy=line.get('cpus_busy'),
                            work_probes_error=line.get('work_probes_error'), sample_error=line.get('sample_error')))
    return dict(schema=SCHEMA + '_SUMMARY', run_dir=str(run_dir), day=day, at=now, stale_after_intervals=STALE_INTERVALS,
                stalled_after_seconds=STALL_SECONDS, stages=out, run_probes=run_probes(run_dir))


def _probe_file(directory, now):
    """One FRANKIE_WORK_PROBE_V1 progress.json read on its own (outside a stage heartbeat): the item, its age, whether
    its writer is the same live process (pid + start ticks), or a status naming why it is not readable."""
    text = _read(Path(directory) / 'progress.json')
    if text is None:
        return dict(dir=str(directory), status='absent')
    try:
        value = json.loads(text)
    except ValueError:
        return dict(dir=str(directory), status='unreadable JSON')
    if not isinstance(value, dict) or value.get('schema') != WORK_PROBE:
        return dict(dir=str(directory), status='not a %s file' % WORK_PROBE)
    item = probe_item(value, directory)
    try:
        item['age_s'] = round(now - float(value.get('at')), 1)
    except (TypeError, ValueError):
        item['age_s'] = None
    pid, token = value.get('pid'), value.get('process_token')
    alive = None
    if isinstance(pid, int) and pid > 0 and token:
        stat = _read('/proc/%d/stat' % pid)
        boot = (_read('/proc/sys/kernel/random/boot_id') or '').strip()
        try:
            fields = stat.rsplit(')', 1)[1].split() if stat else None
            alive = bool(fields) and fields[0] not in ('Z', 'X') and '%s:%s' % (boot, fields[19]) == token
        except IndexError:
            alive = False
    item['process_alive'] = alive
    item['status'] = 'read'
    return item


def run_probes(run_dir, queue_dir=None):
    """The work probes outside any stage child (stacks pass, read-only): the Run's own <run>/progress.json and the queue
    line workers' <line>-worker/progress.json with each line's kick receipt run_settings (FA-6). Absent = 'absent'."""
    now, queue_dir = time.time(), Path(queue_dir or QUEUE_DIR)
    out = [dict(_probe_file(run_dir, now), probe='run')]
    for line in ('root', 'class'):
        item = dict(_probe_file(queue_dir / ('%s-worker' % line), now), probe='%s line worker' % line)
        text = _read(queue_dir / ('%s-kick.json' % line))
        try:
            kick = json.loads(text) if text else None
        except ValueError:
            kick = 'unreadable JSON'
        item['kick'] = (dict(at_utc=kick.get('at_utc'), by=kick.get('by'), scope=kick.get('scope'),
                             run_settings=kick.get('run_settings'), how=kick.get('how'))
                        if isinstance(kick, dict) else kick if kick else 'absent')
        out.append(item)
    return out
