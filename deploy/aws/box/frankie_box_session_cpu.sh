# Read-only CPU probe of the running principal session (classroom, teach, reading): which threads and which Python
# functions are the biggest CPU loads. MODE=threads samples /proc per thread for WINDOW seconds (default 10), labels each
# thread from the classroom helper receipt; MODE=profile adds a nonblocking py-spy sample (same pinned py-spy 0.4.2 as
# frankie_box_root_cpu.sh) with the heaviest functions per thread. EVERY process of the session is covered (Greg,
# 2026-09-28: "it doesn't just have to be one stack ... make sure we get every sub process"): all descendants of every
# thread, recursively (spawn workers, their helpers, shells, git), and py-spy --subprocesses, reported per process. No signals, no pinning, no writes except the
# profile output under /opt/frankie-box/work/performance-session/.
set -eu
MODE="${MODE:-threads}"; SECONDS_WINDOW="${WINDOW:-10}"; TARGET_PID="${PID:-0}"
case "$MODE" in threads|profile) ;; *) echo "MODE must be threads or profile" >&2; exit 2;; esac
case "$TARGET_PID" in *[!0-9]*) echo "PID must be an integer" >&2; exit 2;; esac
case "$SECONDS_WINDOW" in ''|*[!0-9]*) echo "WINDOW must be an integer" >&2; exit 2;; esac
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
exec /opt/frankie-box/venv/bin/python -I -S -B - "$MODE" "$SECONDS_WINDOW" "$TARGET_PID" <<'PY'
import collections, hashlib, io, json, os, subprocess, sys, time, urllib.request, zipfile
from pathlib import Path

mode, window, target = sys.argv[1], max(2, min(60, int(sys.argv[2]))), int(sys.argv[3])
tick = os.sysconf('SC_CLK_TCK')

def stat(path):
    fields = Path(path).read_text().rsplit(')', 1)[1].split()
    return fields[0], int(fields[11]) + int(fields[12])

def comm(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return '?'

# The principal session: frankie_box_boss_session.py, plus any spawn children it owns. PID=<n> probes any one
# frankie-box Python process instead (e.g. a ROOT digest helper).
sessions = []
if target:
    command = (Path('/proc') / str(target) / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
    if '/opt/frankie-box/' not in command or 'python' not in command:
        raise SystemExit('PID must be a frankie-box Python process')
    sessions.append((target, command))
for proc in ([] if target else Path('/proc').iterdir()):
    if not proc.name.isdigit():
        continue
    try:
        command = (proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
    except OSError:
        continue
    if ('frankie_box_boss_session.py' in command or 'run_actual_sunday_ec2.py' in command) and 'python' in command:
        sessions.append((int(proc.name), command))     # the principal session or the cycle launch
if not sessions:
    print(json.dumps(dict(schema='FRANKIE_SESSION_CPU_V1', session=None, note='no principal session process is running')))
    raise SystemExit(0)
def descendants(root):
    """root and every process below it: children of every thread, recursively."""
    seen, queue = [], [root]
    while queue:
        pid = queue.pop(0)
        if pid in seen:
            continue
        seen.append(pid)
        try:
            tasks = list((Path('/proc') / str(pid) / 'task').iterdir())
        except OSError:
            continue
        for task in tasks:
            try:
                queue += [int(x) for x in (task / 'children').read_text().split()]
            except OSError:
                pass
    return seen

pids = []
for pid, _ in sessions:
    pids += [p for p in descendants(pid) if p not in pids]

def session_dir(command):
    parts = command.split()
    return Path(parts[parts.index('--session') + 1]) if '--session' in parts else None

labels = {}
for pid, command in sessions:
    root = session_dir(command)
    for receipt in ([root / 'work' / 'classroom-preparation-workers.json'] if root else []):
        try:
            value = json.loads(receipt.read_bytes())
        except (OSError, ValueError):
            continue
        coordinator = value.get('coordinator') or {}
        for helper in value.get('helpers') or []:
            if 'thread_id' in helper:
                labels[helper['thread_id']] = 'classroom helper cpu %s' % helper.get('cpu')
        if 'thread_id' in coordinator:
            labels[coordinator['thread_id']] = 'classroom coordinator cpu %s' % coordinator.get('cpu')

def threads():
    out = {}
    for pid in pids:
        try:
            for task in (Path('/proc') / str(pid) / 'task').iterdir():
                try:
                    state, ticks = stat(task / 'stat')
                    out[(pid, int(task.name))] = (state, ticks, comm(task / 'comm'))
                except OSError:
                    pass
        except OSError:
            pass
    return out

first, started = threads(), time.monotonic()
time.sleep(window)
last, elapsed = threads(), time.monotonic() - started
rows = []
for key, (state, ticks, name) in last.items():
    before = first.get(key)
    if before is None:
        continue
    pid, tid = key
    try:
        affinity = sorted(os.sched_getaffinity(tid))
    except OSError:
        affinity = []
    cpu = (ticks - before[1]) / tick / elapsed
    rows.append(dict(pid=pid, tid=tid, name=name, state=state, cpu_percent=round(100 * cpu, 1),
                     affinity=affinity if len(affinity) < 8 else 'all(%d)' % len(affinity),
                     label=labels.get(tid, 'main thread' if tid == pid else 'other thread')))
rows.sort(key=lambda r: -r['cpu_percent'])
busy = [r for r in rows if r['cpu_percent'] >= 5]
recent = []
for pid, command in sessions:
    root = session_dir(command)
    if root and (root / 'work').is_dir():
        files = []
        for base, dirs, names in os.walk(root / 'work'):
            dirs[:] = [d for d in dirs if d != 'derived' and not d.startswith('.digest-')]   # ROOT's calculation tree
            for name in names:
                path = Path(base) / name
                try:
                    files.append((path.stat().st_mtime, path))
                except OSError:
                    pass
        recent = [dict(path=str(p.relative_to(root)), age_seconds=round(time.time() - m, 1))
                  for m, p in sorted(files, reverse=True)[:8]]
per_process = collections.defaultdict(float)
for r in rows:
    per_process[r['pid']] += r['cpu_percent']
report = dict(schema='FRANKIE_SESSION_CPU_V1', at=time.time(), seconds=round(elapsed, 2),
              sessions=[dict(pid=pid, command=command[:300]) for pid, command in sessions],
              processes=len(pids), process_cpu_percent={str(k): round(v, 1) for k, v in sorted(per_process.items(), key=lambda kv: -kv[1])},
              threads_total=len(rows), cores_busy=round(sum(r['cpu_percent'] for r in rows) / 100, 2),
              single_core_hot=[r for r in busy if r['cpu_percent'] >= 80],
              busiest=busy, recent_files=recent)

if mode == 'profile':
    out = Path('/opt/frankie-box/work/performance-session')
    tooling = out / 'py-spy-0.4.2'
    tooling.mkdir(parents=True, exist_ok=True)
    binary = tooling / 'py-spy'
    package_sha = 'aeb0323409199c785f730645e9f4bb7a7b9ca2c481f2c331a55642b5d13fa52f'
    url = ('https://files.pythonhosted.org/packages/f9/34/dd7d3c763a00b7b965e25a5eab0acd1a345dbaf0f45fffe595278873a1c0/'
           'py_spy-0.4.2-py2.py3-none-manylinux_2_5_x86_64.manylinux1_x86_64.whl')
    if not binary.exists():
        with urllib.request.urlopen(url, timeout=60) as response:
            wheel = response.read()
        if hashlib.sha256(wheel).hexdigest() != package_sha:
            raise SystemExit('profiler package digest differs')
        with zipfile.ZipFile(io.BytesIO(wheel)) as archive:
            names = [n for n in archive.namelist() if n.endswith('/scripts/py-spy')]
            if len(names) != 1:
                raise SystemExit('one profiler binary required')
            binary.write_bytes(archive.read(names[0]))
        binary.chmod(0o700)
    profiles = []
    for pid, _ in sessions:
        path = out / ('session-%d-%d.json' % (pid, time.time_ns()))
        result = subprocess.run([str(binary), 'record', '--pid', str(pid), '--duration', '20', '--rate', '50',
                                 '--nonblocking', '--threads', '--subprocesses', '--format', 'speedscope', '--output', str(path)],
                                capture_output=True, text=True, timeout=120)
        if result.returncode or not path.exists():
            profiles.append(dict(pid=pid, error=(result.stderr or result.stdout)[-400:]))
            continue
        data = json.loads(path.read_bytes())
        frames = data['shared']['frames']
        per_thread = []
        for stream in data['profiles']:
            inclusive, leaves, total = collections.Counter(), collections.Counter(), 0
            for stack, weight in zip(stream['samples'], stream.get('weights', [1] * len(stream['samples']))):
                if not stack:
                    continue
                total += weight
                leaves[stack[-1]] += weight
                for frame in set(stack):
                    inclusive[frame] += weight
            if not total:
                continue
            def top(counter):
                return [dict(function=frames[i].get('name'), file=(frames[i].get('file') or '')[-80:],
                             line=frames[i].get('line'), percent=round(100 * w / total, 1))
                        for i, w in counter.most_common(8)]
            per_thread.append(dict(thread=stream.get('name'), samples=total, leaf=top(leaves), inclusive=top(inclusive)))
        per_thread.sort(key=lambda t: -t['samples'])
        # every sampled thread of every process (py-spy names each stream 'Process <pid> Thread <tid> ...'), so the
        # workers' stacks are read beside the main thread's
        profiles.append(dict(pid=pid, path=str(path), streams=len(per_thread), threads=per_thread))   # every stream
    report['profile'] = profiles
print(json.dumps(report, indent=1, sort_keys=True))    # whole: ssm_run_sh.py pages anything past 23,000 characters
PY
