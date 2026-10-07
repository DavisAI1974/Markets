# Read existing progress, optionally sample ROOT resource counters. No process control or source write.
# RUN_DIR=/opt/frankie-box/work/experiment/<run> [DAY=YYYYMMDD]: every stage heartbeat of the run (or of one day)
# (frankie_box_stage_progress, FRANKIE_STAGE_HEARTBEAT_V1): last heartbeat age, rate, units, bytes out, files out, rss
# and phase per stage, STALE when a running stage's last line is older than 3 intervals. Read-only; box-progress lock.
set -eu
: "${CODE_ROOT:?existing inactive staged checkout required}"
if [ -n "${RUN_DIR:-}" ]; then
  case "$CODE_ROOT" in /opt/frankie-box/code/*/markets) ;; *) echo "inactive staged checkout required" >&2; exit 2;; esac
  case "$RUN_DIR" in /opt/frankie-box/work/experiment/*) ;; *) echo "RUN_DIR must be under /opt/frankie-box/work/experiment" >&2; exit 2;; esac
  case "$RUN_DIR/" in *"/../"*|*"/./"*) echo "normalized paths required" >&2; exit 2;; esac
  case "${DAY:-}" in ''|[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) echo "DAY must be YYYYMMDD" >&2; exit 2;; esac
  export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
  set -- --run-dir "$RUN_DIR"
  [ -z "${DAY:-}" ] || set -- "$@" --day "$DAY"
  exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_progress.py" "$@"
fi
: "${DIRECTORY:?existing work-probe directory required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*/markets) ;; *) echo "inactive staged checkout required" >&2; exit 2;; esac
case "$DIRECTORY" in /opt/frankie-box/work/*) ;; *) echo "work probe must be under the box work root" >&2; exit 2;; esac
case "$CODE_ROOT/$DIRECTORY/" in *"/../"*|*"/./"*) echo "normalized paths required" >&2; exit 2;; esac
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
case "${RESOURCE_METRICS:-0}" in
  0) exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_progress.py" --directory "$DIRECTORY" ;;
  1) ;;
  *) echo "RESOURCE_METRICS must be 0 or 1" >&2; exit 2;;
esac
# The committed observer is passed directly by the existing SSM route. It needs
# no checkout deployment, package install, tracing attachment or ROOT restart.
exec /opt/frankie-box/venv/bin/python -I -S -B - "$DIRECTORY" <<'PY'
import datetime
import json
import os
from pathlib import Path
import sys
import time

directory = Path(sys.argv[1]).resolve(strict=True)
work = Path('/opt/frankie-box/work').resolve(strict=True)
if not directory.is_relative_to(work):
    raise SystemExit('work directory escapes approved root')
initial = json.loads((directory / 'progress.json').read_text())
pid = initial.get('pid')
if type(pid) is not int or pid <= 0:
    raise SystemExit('valid recorded ROOT PID required')
boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
expected = initial.get('process_token')
proc = Path('/proc') / str(pid)
hz = os.sysconf('SC_CLK_TCK')
device = directory.stat().st_dev
block = Path('/sys/dev/block') / ('%s:%s' % (os.major(device), os.minor(device)))
block = block.resolve(strict=True)
disk = block.parent if (block / 'partition').exists() else block
disk_names = {block.name, disk.name}

def counters(path, selected=None):
    result = {}
    for line in path.read_text().splitlines():
        parts = line.replace(':', '').split()
        if len(parts) >= 2 and (selected is None or parts[0] in selected):
            try:
                result[parts[0]] = int(parts[1])
            except ValueError:
                pass
    return result

def optional_counters(path, selected=None):
    try:
        return counters(path, selected)
    except OSError:
        return None

def projection_files():
    """Metadata only: no source contents, hashes, mutation or tracing."""
    opened = []
    for descriptor in sorted((proc / 'fd').iterdir(), key=lambda p: int(p.name)):
        try:
            target = descriptor.resolve(strict=True)
            if not target.is_relative_to(directory) or not target.is_file():
                continue
            st = target.stat()
            opened.append(dict(fd=int(descriptor.name), path=str(target.relative_to(directory)),
                               bytes=st.st_size,
                               position=counters(proc / 'fdinfo' / descriptor.name, {'pos'}).get('pos')))
        except OSError:
            continue
    statv = os.statvfs(directory)
    spools = [entry for entry in opened if '/.rows/' in entry['path']]
    other = [entry for entry in opened if '/.rows/' not in entry['path']]
    return dict(open_files=other, spool_count=len(spools),
                spool_bytes=sum(entry['bytes'] for entry in spools),
                largest_spools=sorted(spools, key=lambda entry: entry['bytes'], reverse=True)[:5],
                free_bytes=statv.f_bavail * statv.f_frsize,
                affinity=sorted(os.sched_getaffinity(pid)))

def snapshot():
    fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
    token = boot + ':' + fields[19]
    progress = json.loads((directory / 'progress.json').read_text())
    if (token != expected or fields[0] in ('Z', 'X')
            or progress.get('pid') != pid or progress.get('process_token') != expected):
        raise SystemExit('ROOT identity changed or process exited; no interval reported')
    disks = {}
    for line in Path('/proc/diskstats').read_text().splitlines():
        parts = line.split()
        if parts[2] in disk_names:
            disks[parts[2]] = [int(x) for x in parts[3:]]
    pressure = {}
    for kind in ('cpu', 'memory', 'io'):
        try:
            pressure[kind] = {
                parts[0]: dict(pair.split('=', 1) for pair in parts[1:])
                for parts in (line.split() for line in Path('/proc/pressure', kind).read_text().splitlines())
            }
        except OSError:
            pressure[kind] = None
    cgroup = None
    for line in (proc / 'cgroup').read_text().splitlines():
        if line.startswith('0::'):
            base = Path('/sys/fs/cgroup')
            group = (base / line[3:].lstrip('/')).resolve()
            if group.is_relative_to(base):
                cgroup = dict(cpu=optional_counters(group / 'cpu.stat'))
                try:
                    cgroup['cpu_max'] = (group / 'cpu.max').read_text().strip()
                except OSError:
                    cgroup['cpu_max'] = None
    return dict(
        at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        monotonic=time.monotonic(), pid=pid, process_token=token,
        projection_files=projection_files(),
        process=dict(state=fields[0], user_ticks=int(fields[11]), system_ticks=int(fields[12]),
                     major_faults=int(fields[9]), threads=int(fields[17]),
                     io=optional_counters(proc / 'io'),
                     status_kib=counters(proc / 'status', {'VmRSS', 'VmSwap', 'VmSize'})),
        host_cpu_ticks=[int(x) for x in Path('/proc/stat').read_text().splitlines()[0].split()[1:9]],
        memory_kib=counters(Path('/proc/meminfo'), {'MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree', 'Dirty', 'Writeback'}),
        vm=optional_counters(Path('/proc/vmstat'), {'pswpin', 'pswpout', 'pgmajfault'}),
        pressure=pressure, cgroup=cgroup, diskstats=disks,
        progress={key: progress.get(key) for key in ('stage', 'completed', 'total', 'failed', 'at')},
        checkpoints=json.loads((directory / 'checkpoints.json').read_text())
            if (directory / 'checkpoints.json').exists() else None)

model = next((line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
              if line.startswith('model name')), None)
print(json.dumps(dict(schema='FRANKIE_ROOT_RESOURCE_OBSERVATION_V1', clock_ticks=hz,
                      logical_cpus=os.cpu_count(), allowed_cpus=len(os.sched_getaffinity(pid)),
                      cpu_model=model, filesystem_device=block.name, parent_disk=disk.name,
                      interval_seconds=10, intervals=2,
                      scope='Recorded ROOT process; host memory/pressure and shared filesystem disk; read-only counters')),
      flush=True)
for index in range(3):
    if index:
        time.sleep(10)  # Fixed measurement interval, not workflow polling or a workload.
    print(json.dumps(dict(schema='FRANKIE_ROOT_RESOURCE_SAMPLE_V1', sample=index, **snapshot())),
          flush=True)
PY

