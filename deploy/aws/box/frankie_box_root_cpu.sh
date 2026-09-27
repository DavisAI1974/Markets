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
if action not in ('inspect', 'pin', 'profile') or not root.is_relative_to(Path('/opt/frankie-box/work/monday-calculations')):
    raise SystemExit('existing Monday calculation root and inspect/pin/profile action required')
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
if len(workers) < 2:
    raise SystemExit('at least two direct native spawn workers required; found ' + str(len(workers)))
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
              worker_role_note='Native workers identified by direct parent and spawn entry; role names come from runtime receipt, not PID order')
if action == 'profile':
    import collections, io, subprocess, urllib.request, zipfile
    out = root / 'work' / 'performance'
    out.mkdir(exist_ok=True)
    tooling = out / 'py-spy-0.4.2'
    tooling.mkdir(exist_ok=True)
    binary = tooling / 'py-spy'
    package_sha = 'aeb0323409199c785f730645e9f4bb7a7b9ca2c481f2c331a55642b5d13fa52f'
    url = 'https://files.pythonhosted.org/packages/f9/34/dd7d3c763a00b7b965e25a5eab0acd1a345dbaf0f45fffe595278873a1c0/py_spy-0.4.2-py2.py3-none-manylinux_2_5_x86_64.manylinux1_x86_64.whl'
    if not binary.exists():
        with urllib.request.urlopen(url, timeout=60) as response:
            wheel = response.read()
        if hashlib.sha256(wheel).hexdigest() != package_sha:
            raise ValueError('profiler package digest differs')
        with zipfile.ZipFile(io.BytesIO(wheel)) as archive:
            candidates = [n for n in archive.namelist() if n.endswith('/scripts/py-spy')]
            if len(candidates) != 1:
                raise ValueError('one profiler binary required')
            executable = archive.read(candidates[0])
        with binary.open('xb') as stream:
            stream.write(executable)
        binary.chmod(0o700)
        (tooling / 'binary.sha256').write_text(hashlib.sha256(executable).hexdigest() + '\n')
    binary_sha = hashlib.sha256(binary.read_bytes()).hexdigest()
    if (tooling / 'binary.sha256').read_text().strip() != binary_sha:
        raise ValueError('profiler binary digest differs')
    batch = out / ('profile-' + str(time.time_ns()))
    batch.mkdir()
    sessions = []
    started = time.monotonic()
    try:
        for item in processes:
            if identity(item['pid'])['token'] != item['token']:
                raise ValueError('profile process identity differs')
            path = batch / ('pid-' + str(item['pid']) + '.json')
            log = (batch / ('pid-' + str(item['pid']) + '.log')).open('xb')
            command = [str(binary), 'record', '--pid', str(item['pid']),
                       '--duration', '30', '--rate', '50', '--nonblocking',
                       '--format', 'speedscope', '--output', str(path)]
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            sessions.append((item, path, log, child, identity(item['pid'])))
        results = []
        for item, path, log, child, first in sessions:
            code = child.wait(timeout=max(1, 60 - (time.monotonic()-started)))
            log.close()
            last = identity(item['pid'])
            if code != 0 or last['token'] != item['token']:
                raise ValueError('profiler failed or process identity changed; inspect retained profile logs')
            raw = path.read_bytes()
            data = json.loads(raw)
            frames = data['shared']['frames']
            inclusive, leaves = collections.Counter(), collections.Counter()
            total = 0
            for stream in data['profiles']:
                for stack, weight in zip(stream['samples'], stream.get('weights', [1]*len(stream['samples']))):
                    if not stack:
                        continue
                    total += weight
                    leaves[stack[-1]] += weight
                    for frame in set(stack):
                        inclusive[frame] += weight
            def rows(counter):
                return [dict(frame=frames[index], weight=weight,
                             percent=100*weight/total if total else 0)
                        for index,weight in counter.most_common(15)]
            results.append(dict(pid=item['pid'],token=item['token'],
                                path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                                cpu_ticks_delta=last['cpu_ticks']-first['cpu_ticks'],
                                total_weight=total,inclusive=rows(inclusive),leaf=rows(leaves)))
        report = dict(schema='FRANKIE_NATIVE_LIVE_PROFILE_V1',at=time.time(),
                      source_binding_sha256=binding_sha,root=str(root),
                      profiler_version='0.4.2',profiler_wheel_sha256=package_sha,
                      profiler_binary_sha256=binary_sha,nonblocking=True,
                      seconds=30,samples_per_second=50,clock_ticks=os.sysconf('SC_CLK_TCK'),
                      profiles=results,progress=json.loads((root/'progress.json').read_bytes()),
                      limitations=['Sampling observation, not a comparison calculation run',
                                   'Nonblocking Python frames may be incomplete; no native C stack attribution'])
        raw=(json.dumps(report,sort_keys=True,indent=2)+'\n').encode()
        receipt=batch/'profile-receipt.json'
        with receipt.open('xb') as handle:
            handle.write(raw); handle.flush(); os.fsync(handle.fileno())
        if receipt.read_bytes()!=raw:
            raise ValueError('profile receipt readback differs')
        print(json.dumps(dict(receipt_path=str(receipt),bytes=len(raw),
                              sha256=hashlib.sha256(raw).hexdigest(),receipt=report),sort_keys=True))
    finally:
        for item,path,log,child,first in sessions:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=5)
            log.close()
    raise SystemExit(0)

if action == 'inspect':
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0)
if len(unique) < len(processes) + 1:
    raise SystemExit('one distinct physical core per process plus an unassigned core required')
# Leave the first physical core out; allocate three different physical cores.
assignments = [{'pid':item['pid'], 'token':item['token'], 'cpu':core['cpu'],
                'physical_package':core['package'], 'physical_core':core['core'],
                'role':'ROOT' if i == 0 else 'native-worker-' + str(i)}
               for i, (item, core) in enumerate(zip(processes, unique[1:1+len(processes)]))]
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
