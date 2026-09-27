# Assign the identified live ROOT and its two native children to separate physical cores.
# CPU scheduling only: no signals, ingestion, calculation launch or pinned code changes.
set -eu
: "${DIRECTORY:?existing calculation root required}"
: "${EXPECTED_PID:?identified live ROOT PID required}"
: "${EXPECTED_PROCESS_TOKEN:?recorded boot/process identity required}"
: "${BINDING_SHA256:?original source binding required}"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
exec /opt/frankie-box/venv/bin/python -I -S -B - "$DIRECTORY" "${ACTION:-inspect}" \
  "$EXPECTED_PID" "$EXPECTED_PROCESS_TOKEN" "$BINDING_SHA256" <<'PY'
import hashlib, json, os, select, sys, time
from pathlib import Path

root = Path(sys.argv[1]).resolve(strict=True)
action, expected_pid, expected_token, binding_sha = sys.argv[2:6]
pid = int(expected_pid)
if action not in ('inspect', 'pin') or not root.is_relative_to(Path('/opt/frankie-box/work/monday-calculations')):
    raise SystemExit('existing Monday calculation root and inspect/pin action required')
if hashlib.sha256((root / 'source-binding.json').read_bytes()).hexdigest() != binding_sha:
    raise SystemExit('source binding differs')
progress = json.loads((root / 'progress.json').read_bytes())
if (progress.get('pid') != pid or progress.get('process_token') != expected_token
        or progress.get('stage') != 'root-native-records' or progress.get('failed') != 0):
    raise SystemExit('identified healthy forward ROOT required')
boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()

def identity(process):
    fields = (Path('/proc') / str(process) / 'stat').read_text().rsplit(')', 1)[1].split()
    if fields[0] in ('Z', 'X'):
        raise ValueError('process has exited')
    return dict(pid=process, parent_pid=int(fields[1]), token=boot + ':' + fields[19],
                cpu_ticks=int(fields[11]) + int(fields[12]))

def tasks(process):
    return sorted(int(p.name) for p in (Path('/proc') / str(process) / 'task').iterdir())

parent = identity(pid)
if parent['token'] != expected_token:
    raise SystemExit('ROOT identity differs')
children = [int(x) for x in (Path('/proc') / str(pid) / 'task' / str(pid) / 'children').read_text().split()]
workers = []
for child in children:
    command = (Path('/proc') / str(child) / 'cmdline').read_bytes()
    item = identity(child)
    if item['parent_pid'] == pid and b'multiprocessing.spawn' in command and b'spawn_main' in command:
        workers.append(item)
if len(workers) != 2:
    raise SystemExit('exactly two direct native spawn workers required; found ' + str(len(workers)))
workers.sort(key=lambda x: x['pid'])
processes = [parent] + workers
common = set.intersection(*(set(os.sched_getaffinity(x['pid'])) for x in processes))
topology = []
for cpu in sorted(common):
    base = Path('/sys/devices/system/cpu') / ('cpu' + str(cpu)) / 'topology'
    topology.append(dict(cpu=cpu, package=int((base/'physical_package_id').read_text()),
                         core=int((base/'core_id').read_text()),
                         siblings=(base/'thread_siblings_list').read_text().strip()))
unique = []
seen = set()
for item in topology:
    key = (item['package'], item['core'])
    if key not in seen:
        unique.append(item)
        seen.add(key)
before = []
for item in processes:
    item = dict(item)
    thread_ids = tasks(item['pid'])
    item['threads'] = len(thread_ids)
    item['affinity_masks'] = sorted({tuple(sorted(os.sched_getaffinity(t))) for t in thread_ids})
    before.append(item)
report = dict(schema='FRANKIE_ROOT_CPU_ASSIGNMENT_V1', at=time.time(), action=action,
              source_binding_sha256=binding_sha, root=root.as_posix(), processes=before,
              topology=topology, progress=progress,
              worker_role_note='Two native workers identified by direct parent and spawn entry; role names not inferred from PID order')
if action == 'inspect':
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0)
if len(unique) < 4:
    raise SystemExit('four available physical cores required including one left unassigned')
# Leave the first physical core out; allocate three different physical cores.
assignments = [{'pid':item['pid'], 'token':item['token'], 'cpu':core['cpu'],
                'physical_package':core['package'], 'physical_core':core['core'],
                'role':'ROOT' if i == 0 else 'native-worker-' + str(i)}
               for i, (item, core) in enumerate(zip(processes, unique[1:4]))]
fds = {item['pid']:os.pidfd_open(item['pid']) for item in processes}
changes = []
try:
    for item in assignments:
        if identity(item['pid'])['token'] != item['token'] or select.select([fds[item['pid']]], [], [], 0)[0]:
            raise ValueError('process identity changed before affinity assignment')
        for tid in tasks(item['pid']):
            old = sorted(os.sched_getaffinity(tid))
            changes.append((item, tid, old))
            os.sched_setaffinity(tid, {item['cpu']})
    for item in assignments:
        if identity(item['pid'])['token'] != item['token']:
            raise ValueError('process identity changed during affinity assignment')
        if any(os.sched_getaffinity(tid) != {item['cpu']} for tid in tasks(item['pid'])):
            raise ValueError('thread affinity readback differs')
except BaseException:
    for item, tid, old in reversed(changes):
        try:
            if identity(item['pid'])['token'] == item['token']:
                os.sched_setaffinity(tid, old)
        except (OSError, ValueError):
            pass
    raise
finally:
    for fd in fds.values():
        os.close(fd)
report.update(assignments=assignments, readback_verified=True,
              previous_thread_affinities=[dict(pid=item['pid'],token=item['token'],tid=tid,cpus=old)
                                         for item,tid,old in changes],
              numerical_threads_changed=False, calculations_restarted=False,
              limitations=['CPU affinity does not reserve cores against unrelated host processes'])
out = root / 'work' / 'performance'
out.mkdir(exist_ok=True)
path = out / ('cpu-affinity-' + str(pid) + '-' + str(time.time_ns()) + '.json')
raw = (json.dumps(report,sort_keys=True,indent=2)+'\n').encode()
with path.open('xb') as handle:
    handle.write(raw); handle.flush(); os.fsync(handle.fileno())
if path.read_bytes() != raw:
    raise SystemExit('affinity receipt readback differs')
print(json.dumps(dict(receipt_path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                      assignments=assignments,readback_verified=True,
                      calculations_restarted=False),sort_keys=True))
PY
