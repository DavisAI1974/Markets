# Delete staged code nothing uses (Greg, 2026-09-29: "Delete every staged code checkout, transfer pack and ingest
# worktree on the box that nothing uses. That means no running process, no current run's receipt or config, and not
# the newest staged version. Keep one good, complete example of a kind only if deleting would leave none of that kind,
# as a template. Print what it removes and how much space that frees.")
# Kinds: staged checkouts /opt/frankie-box/code/<40 hex>-<run>/, transfer packs /opt/frankie-box/code/transfer-*/,
# ingest worktrees /opt/frankie-box/ingest-code/<40 hex>/. Anything else under those parents is listed, never touched.
# KEPT when any of:
#   process   a running process has its cwd, exe, an open file or a mapped file under it, or names it (or, for an
#             ingest worktree, its commit) in its command line or environment;
#   current   a current run names it (its path, or its commit for a staged checkout / ingest worktree) in a
#             *.json / *.env / *.conf file up to 4 levels deep. A run directory (depth 1 or 2 under work/, plus
#             receipts/) is current when a process has a file open or its cwd in it, or anything in its top two
#             levels changed within RECENT_HOURS (default 24);
#   newest    the newest staged checkout (by its staging-receipt.json), that checkout's transfer pack, and the newest
#             ingest worktree;
#   template  only when a kind would otherwise keep nothing: its newest complete example (checkout with
#             staging-receipt status staged; transfer with transfer-intent.json and source.pack; worktree whose HEAD
#             equals its name).
# MODE=plan (default) is read-only: prints every entry with its bytes and reasons, and DELETE_SHA256 = sha256 of the
# sorted delete names. MODE=delete DELETE_SHA256=<that hash> re-plans, refuses if the delete set differs (named-only)
# or if any file under a delete entry is open, saves each entry's staging/transfer evidence into
# /opt/frankie-box/receipts/code-cleanup-<utc>.json, removes the entries, prunes git worktree metadata, and prints what
# was removed, bytes per kind and the free space before and after. No signals; nothing else is touched.
set -eu
MODE="${MODE:-plan}"; RECENT_HOURS="${RECENT_HOURS:-24}"; DELETE_SHA256="${DELETE_SHA256:-}"
case "$MODE" in plan|delete) ;; *) echo "MODE must be plan or delete" >&2; exit 2;; esac
case "$RECENT_HOURS" in ""|*[!0-9]*) echo "RECENT_HOURS must be an integer" >&2; exit 2;; esac
if [ "$MODE" = delete ]; then
  case "$DELETE_SHA256" in *[!0-9a-f]*) echo "DELETE_SHA256 must be hex" >&2; exit 2;; esac
  [ "${#DELETE_SHA256}" -eq 64 ] || { echo "DELETE_SHA256 (64 hex, from MODE=plan) required" >&2; exit 2; }
fi
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
exec /opt/frankie-box/venv/bin/python -I -S -B - "$MODE" "$RECENT_HOURS" "$DELETE_SHA256" <<'PY'
import hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

mode, recent_hours, want = sys.argv[1], int(sys.argv[2]), sys.argv[3]
ROOT = Path('/opt/frankie-box')
CODE, INGEST, WORK, RECEIPTS = ROOT / 'code', ROOT / 'ingest-code', ROOT / 'work', ROOT / 'receipts'
now = time.time()
HEX40 = re.compile(r'[0-9a-f]{40}')

def size(path):
    total = 0
    for base, dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(base, name)).st_size
            except OSError:
                pass
    return total

def read_json(path):
    try:
        return json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None

# ---- entries
entries, others = [], []
for parent, kinds in ((CODE, ('checkout', 'transfer')), (INGEST, ('worktree',))):
    if not parent.is_dir():
        continue
    for path in sorted(parent.iterdir()):
        name = path.name
        if path.is_symlink() or not path.is_dir():
            others.append(str(path)); continue
        m = re.fullmatch(r'transfer-([0-9a-f]{40})-([A-Za-z0-9_-]{1,96})', name)
        if parent == CODE and m:
            intent = read_json(path / 'transfer-intent.json')
            entries.append(dict(kind='transfer', name='code/' + name, path=path, commit=m.group(1),
                                staged='code/' + m.group(1) + '-' + m.group(2),
                                complete=bool(intent) and (path / 'source.pack').is_file()))
            continue
        m = re.fullmatch(r'([0-9a-f]{40})-([A-Za-z0-9_-]{1,96})', name)
        if parent == CODE and m:
            receipt = read_json(path / 'staging-receipt.json')
            rpath = path / 'staging-receipt.json'
            entries.append(dict(kind='checkout', name='code/' + name, path=path, commit=m.group(1),
                                complete=bool(receipt) and receipt.get('status') == 'staged'
                                and receipt.get('commit') == m.group(1),
                                staged_at=rpath.stat().st_mtime if rpath.is_file() else None))
            continue
        if parent == INGEST and HEX40.fullmatch(name):
            head = subprocess.run(['git', '-C', str(path), 'rev-parse', 'HEAD'], capture_output=True, text=True)
            entries.append(dict(kind='worktree', name='ingest-code/' + name, path=path, commit=name,
                                complete=head.returncode == 0 and head.stdout.strip() == name,
                                staged_at=path.stat().st_mtime))
            continue
        others.append(str(path))
for e in entries:
    e['reasons'] = []

# ---- processes
proc_paths, proc_text, proc_dirs = [], [], set()
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit() or int(proc.name) == os.getpid():
        continue
    try:
        for link in ('cwd', 'exe', 'root'):
            try:
                proc_paths.append(os.readlink(proc / link))
            except OSError:
                pass
        try:
            for fd in (proc / 'fd').iterdir():
                try:
                    proc_paths.append(os.readlink(fd))
                except OSError:
                    pass
        except OSError:
            pass
        try:
            for line in (proc / 'maps').read_text(errors='replace').splitlines():
                parts = line.split(None, 5)
                if len(parts) == 6 and parts[5].startswith('/'):
                    proc_paths.append(parts[5])
        except OSError:
            pass
        for item in ('cmdline', 'environ'):
            try:
                proc_text.append((proc / item).read_bytes().replace(b'\0', b' ').decode(errors='replace'))
            except OSError:
                pass
    except OSError:
        continue
proc_paths = [p.replace(' (deleted)', '') for p in proc_paths]
blob = '\n'.join(proc_text)
for e in entries:
    s = str(e['path'])
    hit = any(p == s or p.startswith(s + '/') for p in proc_paths) or s in blob
    if e['kind'] == 'worktree' and e['commit'] in blob:
        hit = True
    if hit:
        e['reasons'].append('process')

# ---- current runs: run directories touched recently or held by a process
def recent(path):
    cutoff = now - recent_hours * 3600
    try:
        if path.stat().st_mtime >= cutoff:
            return True
        for child in path.iterdir():
            st = child.lstat()
            if st.st_mtime >= cutoff:
                return True
            if child.is_dir() and not child.is_symlink():
                for grand in child.iterdir():
                    if grand.lstat().st_mtime >= cutoff:
                        return True
    except OSError:
        pass
    return False

runs = []
if WORK.is_dir():
    for a in WORK.iterdir():
        if a.is_dir() and not a.is_symlink():
            runs.append(a)
            try:
                runs += [b for b in a.iterdir() if b.is_dir() and not b.is_symlink()]
            except OSError:
                pass
current = []
for run in runs:
    s = str(run)
    held = any(p == s or p.startswith(s + '/') for p in proc_paths)
    if held or recent(run):
        current.append((run, 'held' if held else 'recent'))
current_names = sorted({str(r) for r, _ in current})
texts = []
def scan(base, depth):
    try:
        for child in base.iterdir():
            if child.is_symlink():
                continue
            if child.is_dir():
                if depth > 1 and child.name not in ('derived', 'blocks', '.projection-v2') and not child.name.startswith('.digest'):
                    scan(child, depth - 1)
            elif child.suffix in ('.json', '.env', '.conf') and child.stat().st_size <= 8 << 20:
                try:
                    texts.append((str(child), child.read_text(errors='replace')))
                except OSError:
                    pass
    except OSError:
        pass
for run, _ in current:
    if run.parent == WORK:
        scan(run, 4)
if RECEIPTS.is_dir():
    cutoff = now - recent_hours * 3600
    for child in RECEIPTS.rglob('*'):
        try:
            if child.is_file() and child.stat().st_mtime >= cutoff and child.stat().st_size <= 8 << 20:
                texts.append((str(child), child.read_text(errors='replace')))
        except OSError:
            pass
for e in entries:
    keys = [str(e['path'])]
    if e['kind'] in ('checkout', 'worktree'):
        keys.append(e['commit'])
    refs = sorted({path for path, text in texts if any(k in text for k in keys)})
    if refs:
        e['reasons'].append('current')
        e['referenced_by'] = refs[:5]

# ---- newest
checkouts = [e for e in entries if e['kind'] == 'checkout' and e['complete']]
if checkouts:
    newest = max(checkouts, key=lambda e: e['staged_at'])
    newest['reasons'].append('newest')
    for e in entries:
        if e['kind'] == 'transfer' and e['staged'] == newest['name']:
            e['reasons'].append('newest')
worktrees = [e for e in entries if e['kind'] == 'worktree' and e['complete']]
if worktrees:
    max(worktrees, key=lambda e: e['staged_at'])['reasons'].append('newest')
# a checkout kept for any reason keeps its transfer pack only when the pack is still being staged (no receipt yet)
for e in entries:
    if e['kind'] == 'checkout' and not e['complete'] and not e['reasons']:
        if any(t['kind'] == 'transfer' and t['staged'] == e['name'] and t['reasons'] for t in entries):
            e['reasons'].append('staging')

# ---- template: only when a kind would keep nothing
for kind in ('checkout', 'transfer', 'worktree'):
    items = [e for e in entries if e['kind'] == kind]
    if items and not any(e['reasons'] for e in items):
        good = [e for e in items if e['complete']]
        if good:
            key = (lambda e: e['path'].stat().st_mtime)
            max(good, key=key)['reasons'].append('template')

for e in entries:
    e['bytes'] = size(e['path'])
delete = sorted(e['name'] for e in entries if not e['reasons'])
digest = hashlib.sha256('\n'.join(delete).encode()).hexdigest()

def summary(items):
    out = {}
    for kind in ('checkout', 'transfer', 'worktree'):
        k = [e for e in items if e['kind'] == kind]
        out[kind] = dict(count=len(k), bytes=sum(e['bytes'] for e in k))
    return out

def free():
    st = os.statvfs(ROOT)
    return st.f_bavail * st.f_frsize

print('### current run directories (%d, RECENT_HOURS=%d)' % (len(current), recent_hours))
for r, why in sorted(current, key=lambda x: str(x[0])):
    print('  %-6s %s' % (why, r))
print('### entries (kind, bytes, KEEP reasons or DELETE, name)')
for e in sorted(entries, key=lambda e: (e['kind'], e['name'])):
    print('  %-8s %14d  %-28s %s%s' % (e['kind'], e['bytes'], 'KEEP ' + '+'.join(e['reasons']) if e['reasons'] else 'DELETE',
                                    e['name'], '' if e['complete'] else '  (incomplete)'))
    for ref in e.get('referenced_by', []):
        print('             referenced by %s' % ref)
if others:
    print('### not a known kind, untouched: %s' % ' '.join(others))
kept = [e for e in entries if e['reasons']]
gone = [e for e in entries if not e['reasons']]
print(json.dumps(dict(schema='FRANKIE_CLEANUP_CODE_PLAN_V1', mode=mode, keep=summary(kept), delete=summary(gone),
                      delete_bytes=sum(e['bytes'] for e in gone), delete_count=len(delete),
                      free_bytes=free(), DELETE_SHA256=digest), sort_keys=True))
if mode == 'plan':
    sys.exit(0)

if want != digest:
    raise SystemExit('the delete set differs from the planned one (%s != %s); nothing removed' % (digest, want))
busy = [(e['name'], p) for e in gone for p in proc_paths if p == str(e['path']) or p.startswith(str(e['path']) + '/')]
if busy:
    raise SystemExit('files in use, nothing removed: %s' % json.dumps(busy[:10]))
before = free()
evidence = []
for e in gone:
    item = dict(kind=e['kind'], name=e['name'], path=str(e['path']), bytes=e['bytes'], commit=e['commit'])
    for fname in ('staging-intent.json', 'staging-receipt.json', 'transfer-intent.json', 'cache-removal-receipt.json'):
        v = read_json(e['path'] / fname)
        if v is not None:
            item[fname] = v
    evidence.append(item)
RECEIPTS.mkdir(parents=True, exist_ok=True)
stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
receipt = RECEIPTS / ('code-cleanup-%s.json' % stamp)
with open(receipt, 'x') as out:
    json.dump(dict(schema='FRANKIE_CLEANUP_CODE_RECEIPT_V1', at=stamp, delete_sha256=digest, removed=evidence,
                   kept=[dict(name=e['name'], reasons=e['reasons'], bytes=e['bytes']) for e in kept],
                   free_bytes_before=before), out, sort_keys=True, indent=1)
    out.flush(); os.fsync(out.fileno())
removed = []
for e in gone:
    shutil.rmtree(e['path'])
    removed.append(e)
    print('removed %-8s %14d  %s' % (e['kind'], e['bytes'], e['path']))
if any(e['kind'] == 'worktree' for e in removed) and (ROOT / 'markets' / '.git').exists():
    subprocess.run(['git', '-C', str(ROOT / 'markets'), 'worktree', 'prune'], check=False)
after = free()
print(json.dumps(dict(schema='FRANKIE_CLEANUP_CODE_V1', receipt=str(receipt), removed=summary(removed),
                      removed_bytes=sum(e['bytes'] for e in removed), free_bytes_before=before,
                      free_bytes_after=after, freed_bytes=after - before), sort_keys=True))
PY
