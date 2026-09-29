# Free disk from failed or superseded digest table work of one Monday calculation root (Greg, 2026-09-28: the failed
# bedrock side builds filled the 2 TB disk). Deletes ONLY what is named, and only when nothing of it was saved:
#   SIDE_DIRS   comma-separated .digest-side-<id> directory names under work/derived: each must hold no
#               table-*.save.json (no finished table) and no file any running process has open.
#   SCRATCHES   optional comma-separated .digest-<32 hex> scratch directories under work/derived that never saved a
#               table (no table-*.save.json anywhere in them): abandoned digest attempts (Greg, 2026-09-29: "Clean the
#               disk out now first quickly. Use process we used yesterday."). Same rules: refused if any table was
#               saved, if any file under it is open, or if the calculation root is locked (ROOT running).
#   PARTIAL     optional <.digest-hex>:<NNNN>: that scratch's table-NNNN.txt and table-NNNN/ (a table the paused ROOT
#               was still writing): refused if table-NNNN.save.json exists or the calculation root is locked (ROOT
#               running).
# Prints what was removed with its bytes, then the free space. No signals; nothing else is touched.
set -eu
: "${DIRECTORY:?Monday calculation root required}"
case "$DIRECTORY" in /opt/frankie-box/work/monday-calculations/*) ;; *) echo "Monday calculation root required" >&2; exit 2;; esac
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
exec /opt/frankie-box/venv/bin/python -I -S -B - "$DIRECTORY" "${SIDE_DIRS:-}" "${PARTIAL:-}" "${SCRATCHES:-}" <<'PY'
import fcntl, json, os, re, shutil, sys
from pathlib import Path

root = Path(sys.argv[1]).resolve(strict=True)
derived = root / 'work' / 'derived'
side_names = [n for n in sys.argv[2].split(',') if n]
partial = sys.argv[3]

def size(path):
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob('*') if p.is_file() and not p.is_symlink())

def open_under(path):
    """(pid, file) of any process holding a file under path."""
    prefix = str(path) + '/'
    found = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            for fd in (proc / 'fd').iterdir():
                try:
                    target = os.readlink(fd)
                except OSError:
                    continue
                if target == str(path) or target.startswith(prefix):
                    found.append((int(proc.name), target))
        except OSError:
            continue
    return found

plan = []
for name in side_names:
    if not re.fullmatch(r'\.digest-side-[0-9TZ]+', name):
        raise SystemExit('side directory name must be .digest-side-<id>: %r' % name)
    path = derived / name
    if path.is_symlink() or not path.is_dir() or path.resolve().parent != derived:
        raise SystemExit('not a side directory of this root: %s' % path)
    saved = sorted(p.name for p in path.glob('table-*.save.json'))
    if saved:
        raise SystemExit('%s holds finished tables %s; refusing' % (name, saved))
    plan.append(path)

scratch_names = [n for n in (sys.argv[4] if len(sys.argv) > 4 else '').split(',') if n]
if scratch_names:
    lock_all = (root / 'calculation.lock').open('a')
    try:
        fcntl.flock(lock_all, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('the calculation root is locked: ROOT is running') from None
for name in scratch_names:
    if not re.fullmatch(r'\.digest-[0-9a-f]{32}', name):
        raise SystemExit('scratch name must be .digest-<32 hex>: %r' % name)
    path = derived / name
    if path.is_symlink() or not path.is_dir() or path.resolve().parent != derived:
        raise SystemExit('not a digest scratch of this root: %s' % path)
    saved = sorted(str(p.relative_to(path)) for p in path.rglob('table-*.save.json'))
    if saved:
        raise SystemExit('%s saved tables %s; refusing' % (name, saved[:5]))
    plan.append(path)

if partial:
    m = re.fullmatch(r'(\.digest-[0-9a-f]{32}):(\d{4})', partial)
    if m is None:
        raise SystemExit('PARTIAL must be .digest-<32 hex>:<NNNN>')
    scratch = derived / m.group(1)
    if scratch.is_symlink() or not scratch.is_dir() or scratch.resolve().parent != derived:
        raise SystemExit('not a digest scratch of this root: %s' % scratch)
    if (scratch / ('table-%s.save.json' % m.group(2))).exists():
        raise SystemExit('table %s was saved; refusing' % m.group(2))
    lock = (root / 'calculation.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('the calculation root is locked: ROOT is running') from None
    for item in (scratch / ('table-%s.txt' % m.group(2)), scratch / ('table-%s' % m.group(2))):
        if item.exists() and not item.is_symlink():
            plan.append(item)

busy = [(str(p), open_under(p)) for p in plan]
busy = [(p, files[:5]) for p, files in busy if files]
if busy:
    raise SystemExit('files in use, nothing removed: %s' % json.dumps(busy))
removed = []
for path in plan:
    bytes_ = size(path)
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    removed.append(dict(path=str(path), bytes=bytes_))
stat = os.statvfs(root)
print(json.dumps(dict(schema='FRANKIE_CLEANUP_SIDE_V1', removed=removed,
                      removed_bytes=sum(r['bytes'] for r in removed),
                      free_bytes=stat.f_bavail * stat.f_frsize), indent=1))
PY
