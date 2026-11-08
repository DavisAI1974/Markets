"""Replace a one-helper projection pool, retaining sealed stages and range files."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

day = sys.argv[1]
assert day in ('20231002', '20231003', '20231017')
base = Path('/opt/frankie-box')
control = base/'replay-control'
logs = control/day
root = base/'work/experiment-roots'/f'ng-replay-{day}'
lock = (logs/'projection-affinity-recovery.lock').open('a')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
progress = json.loads((root/'progress.json').read_bytes())
assert progress['stage'] == 'root-projection-member', progress
pid = progress['pid']
cmd = Path(f'/proc/{pid}/cmdline').read_bytes().decode().split('\0')
assert '--output-root' in cmd and cmd[cmd.index('--output-root')+1] == str(root), cmd
assert (root/'work/native-stage.json').is_file()
projection = root/'work/derived/.projection-v2'
workers = json.loads((projection/f'workers-{pid}.json').read_bytes())
assert len(workers['lane']) == len(workers['helpers']) == 1, workers
helper = workers['helpers'][0]['pid']
assert f'PPid:\t{pid}\n' in Path(f'/proc/{helper}/status').read_text()
deployment = json.loads((logs/'touch-print-gate-deployment.json').read_bytes())
waiter = deployment['waiter_pid']
assert (logs/'standalone-status').read_text().strip().endswith('waiting-for-producers')
assert str(deployment['waiter']).encode() in Path(f'/proc/{waiter}/cmdline').read_bytes()
before = dict(observed_at=time.time(), progress=progress, workers=workers,
              completed_ranges=len(list((projection/'member').glob('range-*.json'))),
              native_stage_mtime_ns=(root/'work/native-stage.json').stat().st_mtime_ns)
saved = logs/f'projection-lane-before-{pid}.json'
saved.write_text(json.dumps(before, indent=2)+'\n')
os.kill(waiter, signal.SIGSTOP)
try:
    # The nohup coordinator ignores SIGINT and defers SIGTERM until after projection.
    # Ending its sole helper raises BrokenProcessPool and lets ROOT unwind its locks.
    # A partially written range stays unreceipted; completed ranges remain reusable.
    os.kill(helper, signal.SIGTERM)
    for _ in range(100):
        if not Path(f'/proc/{pid}').exists():
            break
        time.sleep(.2)
    else:
        raise RuntimeError('old ROOT did not exit; no replacement launched')
    subprocess.run(['flock', '-w', '5', str(logs/'job.lock'), 'true'], check=True)
    shutil.copyfile(logs/'root.log', logs/f'root.pre-lane-{pid}.log')
    env = dict(os.environ, FRANKIE_REPLAY_PYTHON='/opt/replay-runtime/venv/bin/python',
               FRANKIE_REPLAY_BOOTSTRAP=str(control/'runpod_root_bootstrap.py'))
    with (logs/'projection-lane-recovery.log').open('ab') as output:
        process = subprocess.Popen(['bash', str(control/'runpod_replay_discovery_compat.sh'), day,
                                    '--after-ingest'], env=env, stdin=subprocess.DEVNULL,
                                   stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(100):
        state = (logs/'status').read_text().split(maxsplit=1)[1].strip()
        if state in ('waiting-for-runtime', 'preflight', 'root-native', 'producer-handoff-sealed'):
            break
        if process.poll() is not None:
            raise RuntimeError(f'replacement exited {process.returncode}')
        time.sleep(.2)
    else:
        raise RuntimeError('replacement status did not advance')
    print(day, 'resuming with full CPU lane; retained member ranges', before['completed_ranges'], flush=True)
finally:
    os.kill(waiter, signal.SIGCONT)

for _ in range(240):
    fresh = json.loads((root/'progress.json').read_bytes())
    if fresh['pid'] != pid and fresh['stage'].startswith('root-projection-'):
        worker_file = projection/f"workers-{fresh['pid']}.json"
        if worker_file.is_file():
            after = json.loads(worker_file.read_bytes())
            if len(after['helpers']) != len(os.sched_getaffinity(0))-1:
                raise RuntimeError(('replacement pool still undersized', after))
            assert (root/'work/native-stage.json').stat().st_mtime_ns == before['native_stage_mtime_ns']
            result = dict(before=saved.name, resumed_at=time.time(), progress=fresh, workers=after,
                          native_stage_reused_unchanged=True, bootstrap_revision='8ff32c2f5')
            (logs/'projection-lane-recovery.json').write_text(json.dumps(result, indent=2)+'\n')
            print(json.dumps(result), flush=True)
            break
    time.sleep(.25)
else:
    raise RuntimeError('new worker map not yet visible; inspect recovery log before any retry')
