# Greg, 2026-09-30 ("stop the waiting worker"): end a ROOT-line worker that is WAITING on the line's lock (started by
# frankie_box_frankie_queue.sh ACTION=handover with --wait-lock) before it takes the line over. A control step only:
# it changes no process code and never touches the running worker (the lock holder), a running day, a ROOT or a file.
# A --wait-lock worker that already holds the lock is running the line: refused (never stop a running job).
# Receipt: /opt/frankie-box/receipts/stop-waiting-worker-<utc>.json. Read-only when none waits. SSM runs this under sh.
set -eu
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
exec /opt/frankie-box/venv/bin/python -I -S -B - <<'PY'
import json, os, signal, time
from pathlib import Path

queue = Path('/opt/frankie-box/work/frankie-queue')
status_path = queue / 'root-worker.json'
status = json.loads(status_path.read_bytes()) if status_path.is_file() else {}
running_pid = status.get('pid')
me = os.getpid()


def waiting():
    out = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name) == me:
            continue
        try:
            cmd = (proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
        except OSError:
            continue
        if 'frankie_box_frankie_queue.py' in cmd and '--action worker' in cmd and '--line root' in cmd and '--wait-lock' in cmd:
            out.append(dict(pid=int(proc.name), command=cmd.strip()))
    return out


found = waiting()
receipt = dict(schema='FRANKIE_STOP_WAITING_WORKER_V1', at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               running_worker=dict(pid=running_pid, state=status.get('state'), commit=status.get('commit')),
               found=found, stopped=[], refused=[])
for w in found:
    if w['pid'] == running_pid:
        receipt['refused'].append(dict(w, reason='this worker holds the lock and runs the line (never stop a running job)'))
        continue
    os.kill(w['pid'], signal.SIGTERM)
    receipt['stopped'].append(w)
time.sleep(10)
receipt['still_alive'] = [w for w in waiting() if w['pid'] in {s['pid'] for s in receipt['stopped']}]
receipt['after'] = waiting()
out = Path('/opt/frankie-box/receipts') / ('stop-waiting-worker-%s.json' % receipt['at'].replace(':', ''))
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(receipt, indent=1, sort_keys=True) + '\n', encoding='utf-8')
print(json.dumps(receipt, indent=1, sort_keys=True))
print('receipt', out)
PY
