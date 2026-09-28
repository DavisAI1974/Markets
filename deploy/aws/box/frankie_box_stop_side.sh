# Stop a running bedrock side builder (frankie_box_bedrock_side.py) of one Monday calculation root, with its helper
# processes, so it can be restarted (for example on more CPUs). Tables it already finished keep their save receipts
# in work/derived/.digest-side-<id>/ and a restarted side builder or ROOT reuses them. ROOT is never touched: only
# processes whose command is the side builder for DIRECTORY, and their descendants, are signalled.
# Inputs: DIRECTORY (Monday calculation root). SIGTERM, then SIGKILL after 30 s for anything left.
set -eu
: "${DIRECTORY:?Monday calculation root required}"
case "$DIRECTORY" in /opt/frankie-box/work/monday-calculations/*) ;; *) echo "Monday calculation root required" >&2; exit 2;; esac
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
exec /opt/frankie-box/venv/bin/python -I -S -B - "$DIRECTORY" <<'PY'
import json, os, signal, sys, time
from pathlib import Path

directory = sys.argv[1]

def command(pid):
    try:
        return (Path('/proc') / str(pid) / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
    except OSError:
        return None

def children(pid):
    out = []
    try:
        for task in (Path('/proc') / str(pid) / 'task').iterdir():
            out += [int(x) for x in (task / 'children').read_text().split()]
    except OSError:
        pass
    return out

roots = []
for proc in Path('/proc').iterdir():
    if proc.name.isdigit():
        text = command(int(proc.name)) or ''
        if ('frankie_box_bedrock_side.py' in text and '/opt/frankie-box/' in text
                and ('--directory ' + directory + ' ') in text + ' '):
            roots.append(int(proc.name))
targets = []
for pid in roots:
    stack = [pid]
    while stack:
        current = stack.pop()
        if current not in targets:
            targets.append(current)
            stack += children(current)
report = dict(schema='FRANKIE_STOP_SIDE_V1', directory=directory, side_builders=roots,
              targets=[dict(pid=p, command=(command(p) or '')[:200]) for p in targets])
for pid in targets:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
deadline = time.monotonic() + 30
while time.monotonic() < deadline and any(command(p) for p in targets):
    time.sleep(1)
killed = []
for pid in targets:
    if command(pid):
        try:
            os.kill(pid, signal.SIGKILL)
            killed.append(pid)
        except ProcessLookupError:
            pass
time.sleep(1)
report.update(killed_after_timeout=killed, still_alive=[p for p in targets if command(p)])
print(json.dumps(report, indent=1))
PY
