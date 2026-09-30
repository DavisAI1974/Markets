# Greg, 2026-09-30 ("stop the days for a little bit once they finish ROOT's part without starting any new days"): end
# an experiment orchestrator start of RUN (frankie_box_experiment.py --action start --run RUN, detached or not) while it
# only WAITS (no step running: no child process), so it cannot kick a ROOT-line worker and start new days. A control
# step only: no process code changed, nothing deleted; every finished step keeps its receipt and a later start skips it.
# An orchestrator with a running step (a child process) is refused (never stop a running job).
# Inputs: RUN. Receipt: /opt/frankie-box/receipts/stop-orchestrator-<RUN>-<utc>.json. SSM runs this under sh.
set -eu
: "${RUN:?the orchestrator run name required}"
case "$RUN" in ""|*[!A-Za-z0-9_-]*) echo "RUN: letters, digits, _ and - only" >&2; exit 2;; esac
export RUN PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
exec /opt/frankie-box/venv/bin/python -I -S -B - <<'PY'
import json, os, signal, time
from pathlib import Path

run = os.environ['RUN']
me = os.getpid()


def procs():
    rows = {}
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            cmd = (proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace').strip()
            ppid = int((proc / 'stat').read_text().rsplit(')', 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            continue
        rows[int(proc.name)] = dict(cmd=cmd, ppid=ppid)
    return rows


def starts(rows):
    key = 'frankie_box_experiment.py --action start --run %s ' % run
    return [p for p, r in rows.items() if p != me and key in r['cmd'] + ' ']


rows = procs()
found = starts(rows)
receipt = dict(schema='FRANKIE_STOP_ORCHESTRATOR_V1', run=run, at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               found=[dict(pid=p, command=rows[p]['cmd']) for p in found], stopped=[], refused=[])
for p in found:
    children = [dict(pid=c, command=r['cmd']) for c, r in rows.items() if r['ppid'] == p]
    if children:
        receipt['refused'].append(dict(pid=p, children=children, reason='a step is running under it (never stop a running job)'))
        continue
    os.kill(p, signal.SIGTERM)
    receipt['stopped'].append(dict(pid=p))
time.sleep(5)
receipt['after'] = [dict(pid=p, command=r['cmd']) for p, r in procs().items() if p in starts(procs())]
out = Path('/opt/frankie-box/receipts') / ('stop-orchestrator-%s-%s.json' % (run, receipt['at'].replace(':', '')))
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(receipt, indent=1, sort_keys=True) + '\n', encoding='utf-8')
print(json.dumps(receipt, indent=1, sort_keys=True))
print('receipt', out)
PY
