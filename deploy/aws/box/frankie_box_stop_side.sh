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


def wait_exit(pids, bound):
    """2026-10-09 (no fixed waits): block until every pid has exited or `bound` seconds passed (the grace before KILL);
    returns at the last exit. One pidfd per pid (Linux >= 5.3); without pidfd_open the bound itself is the wait."""
    import select
    deadline, fds = time.monotonic() + bound, {}
    for p in set(pids):
        try:
            fds[os.pidfd_open(p)] = p
        except ProcessLookupError:
            pass
        except (OSError, AttributeError):
            time.sleep(max(0.0, deadline - time.monotonic()))
            return
    while fds:
        left = deadline - time.monotonic()
        if left <= 0:
            break
        poll = select.poll()
        for fd in fds:
            poll.register(fd, select.POLLIN)
        for fd, _ in poll.poll(int(left * 1000)):
            os.close(fd)
            fds.pop(fd, None)
    for fd in fds:
        os.close(fd)

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
wait_exit(targets, 30)   # returns at the last exit (30 s grace at most), never a 1 s poll
killed = []
for pid in targets:
    if command(pid):
        try:
            os.kill(pid, signal.SIGKILL)
            killed.append(pid)
        except ProcessLookupError:
            pass
wait_exit(killed, 5)
report.update(killed_after_timeout=killed, still_alive=[p for p in targets if command(p)])
print(json.dumps(report, indent=1))
PY
