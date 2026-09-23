# Interrupt only an identified read-only source-authoring process. Preserve every file.
set -eu
: "${DIRECTORY:?source authoring directory required}"
: "${AUTHOR_CODE_ROOT:?exact authoring checkout required}"
: "${AUTHOR_COMMIT:?exact authoring commit required}"
export DIRECTORY AUTHOR_CODE_ROOT AUTHOR_COMMIT
exec /opt/frankie-box/venv/bin/python -B - <<'PY'
import json, os, signal, time
from pathlib import Path
root = Path(os.environ['DIRECTORY'])
code = Path(os.environ['AUTHOR_CODE_ROOT'])
if (root.parent != Path('/opt/frankie-box/work/monday-launch')
        or not str(code).startswith('/opt/frankie-box/code/') or code.name != 'markets'
        or '..' in root.parts or '..' in code.parts):
    raise SystemExit('explicit source-authoring paths required')
probe = json.loads((root/'progress.json').read_bytes())
pid = probe['pid']
if type(pid) is not int or pid <= 1 or probe['request_sha256'] != os.environ['AUTHOR_COMMIT']:
    raise SystemExit('authoring process identity differs')
def identity(n):
    try:
        fields = (Path('/proc')/str(n)/'stat').read_text().rsplit(')',1)[1].split()
        return int(fields[1]), fields[19]
    except FileNotFoundError:
        return None
boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
observed = identity(pid)
if observed is None:
    print(json.dumps(dict(status='already_exited', pid=pid)))
    raise SystemExit(0)
if probe['process_token'] != boot + ':' + observed[1]:
    raise SystemExit('PID was reused; no signal sent')
argv = (Path('/proc')/str(pid)/'cmdline').read_bytes().split(b'\0')
expected = [str(code/'deploy/aws/box/frankie_box_author_monday_launch.py'),
            '--commit', os.environ['AUTHOR_COMMIT'], '--output-root', str(root)]
joined = [v.decode() for v in argv if v]
if not any(joined[i:i+len(expected)] == expected for i in range(len(joined))):
    raise SystemExit('process is not the declared read-only author; no signal sent')
known = {}
for item in Path('/proc').glob('[0-9]*'):
    value = identity(int(item.name))
    if value is not None:
        known[int(item.name)] = value
targets = {pid: observed}
while True:
    found = {n:v for n,v in known.items() if v[0] in targets and n not in targets}
    if not found:
        break
    targets.update(found)
receipt = dict(schema='FRANKIE_SOURCE_AUTHOR_INTERRUPTION_V1', at=time.time(), pid=pid,
    process_token=probe['process_token'], progress=probe,
    reason='Replace redundant full-book source-metadata reads with the existing verified conformance projection.',
    scope='this read-only author and its workers only; no ingestion, service or infrastructure action',
    files_deleted=0, signals=[])
path = root / ('interruption-' + str(time.time_ns()) + '.json')
for n, expected_identity in targets.items():
    current = identity(n)
    if current is not None and current[1] == expected_identity[1]:
        try:
            os.kill(n, signal.SIGTERM)
            receipt['signals'].append(n)
        except ProcessLookupError:
            pass
with path.open('x',encoding='utf-8') as f:
    json.dump(receipt,f,sort_keys=True)
print(json.dumps(dict(status='signals_sent', receipt=str(path), pids=receipt['signals'])))
PY
