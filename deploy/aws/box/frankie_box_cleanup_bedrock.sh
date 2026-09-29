# Delete the Monday root's bedrock tables and projection working files (Greg, 2026-09-29: "bedrock table gets
# deleted. We already have this data."). Named-only: TARGETS is a comma list of names relative to <root>/work/derived:
#   .digest-<32 hex>                  a whole digest render scratch
#   .digest-<32 hex>/table-NNNN       one UNSAVED table of a scratch (its table-NNNN/ and table-NNNN.txt); refused when
#                                     table-NNNN.save.json exists
#   .digest-side-work | .digest-side-<id>   the side builder's bedrock tables
#   .projection-v2/published-<32 hex> | .projection-v2/member | .projection-v2/lifecycle   projection outputs/archives
#   @work/bedrock (alone)             the whole <root>/work/bedrock (Greg: "Delete all 818 of bedrock. None of it is
#                                     needed"); only the open-file and lock refusals apply
# Refused (nothing removed) when: the root's calculations receipt is not calculations_retained with bedrock tables
# "retained in the layer files"; any pinned ledger, derive.json, digest or the moved-aside digest is missing or differs
# in size (derive.json and the digest proof also by sha256); a target is named by any *.json outside work/derived under
# /opt/frankie-box/work or /opt/frankie-box/receipts (so the published layer files derive.json pins, and a scratch a CLM
# manifest reads, are never taken); a file under a target is open; the calculation root is locked (ROOT running).
# Every *.json up to 4 MiB inside a target is copied to /opt/frankie-box/receipts/bedrock-cleanup-<utc>/ with the receipt.
# MODE=plan (default) is read-only and prints the same checks and sizes; MODE=delete removes. Prints removed paths,
# their bytes and the free space before and after. No signals.
set -eu
: "${DIRECTORY:?Monday calculation root required}"
: "${TARGETS:?comma list of targets under work/derived required}"
MODE="${MODE:-plan}"
case "$MODE" in plan|delete) ;; *) echo "MODE must be plan or delete" >&2; exit 2;; esac
case "$DIRECTORY" in /opt/frankie-box/work/monday-calculations/*) ;; *) echo "Monday calculation root required" >&2; exit 2;; esac
case "$DIRECTORY$TARGETS" in *..*) echo "no .. allowed" >&2; exit 2;; esac
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
exec /opt/frankie-box/venv/bin/python -I -S -B - "$MODE" "$DIRECTORY" "$TARGETS" <<'PY'
import fcntl, hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

mode, root, targets = sys.argv[1], Path(sys.argv[2]).resolve(strict=True), [t for t in sys.argv[3].split(',') if t]
BOX = Path('/opt/frankie-box')
derived = root / 'work' / 'derived'
ALLOWED = [r'\.digest-[0-9a-f]{32}', r'\.digest-[0-9a-f]{32}/table-\d{4}', r'\.digest-side-[A-Za-z0-9TZ-]+',
           r'\.projection-v2/published-[0-9a-f]{32}', r'\.projection-v2/(member|lifecycle)']

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()

def size(path):
    if path.is_file():
        return path.lstat().st_size
    total = 0
    for base, dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(base, name)).st_size
            except OSError:
                pass
    return total

def free():
    st = os.statvfs(BOX)
    return st.f_bavail * st.f_frsize

# ---- TARGETS=@work/bedrock: the whole bedrock directory (Greg, 2026-09-29: "Delete all 818 of bedrock. None of it is
# needed"). No retained-copy gate and no reference refusal (his call); still refused on an open file or a locked root.
# The *.json files naming it are listed in the receipt for the record.
if targets == ['@work/bedrock']:
    whole = root / 'work' / 'bedrock'
    if whole.is_symlink() or not whole.is_dir():
        raise SystemExit('no bedrock directory: %s' % whole)
    held = []
    for proc in Path('/proc').iterdir():
        if proc.name.isdigit():
            try:
                for fd in (proc / 'fd').iterdir():
                    try:
                        t = os.readlink(fd)
                    except OSError:
                        continue
                    if t.startswith(str(whole) + '/'):
                        held.append((int(proc.name), t))
            except OSError:
                pass
    if held:
        raise SystemExit('files in use, nothing removed: %s' % json.dumps(held[:10]))
    lock = (root / 'calculation.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('the calculation root is locked: ROOT is running') from None
    named = subprocess.run(['grep', '-rlF', '--include=*.json', str(whole), str(BOX / 'work'), str(BOX / 'receipts')],
                           capture_output=True, text=True).stdout.split()
    named = [n for n in named if not n.startswith(str(whole) + '/')]
    parts = sorted(((size(p), p.name) for p in whole.iterdir()), reverse=True)
    total = sum(s for s, _ in parts)
    for s, n in parts:
        print('  %14d  work/bedrock/%s' % (s, n))
    print(json.dumps(dict(schema='FRANKIE_CLEANUP_BEDROCK_PLAN_V1', mode=mode, target='work/bedrock', target_bytes=total,
                          named_by=len(named), free_bytes=free()), sort_keys=True))
    if mode == 'plan':
        sys.exit(0)
    before = free()
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    keep = BOX / 'receipts' / ('bedrock-whole-%s' % stamp)
    keep.mkdir(parents=True)
    saved = 0
    for base, dirs, files in os.walk(whole):
        for name in files:
            f = Path(base) / name
            if name.endswith('.json') and f.lstat().st_size <= 4 << 20:
                dest = keep / f.relative_to(root / 'work')
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)
                saved += 1
    shutil.rmtree(whole)
    after = free()
    out = dict(schema='FRANKIE_CLEANUP_BEDROCK_WHOLE_V1', at=stamp, removed=str(whole), removed_bytes=total,
               parts=[dict(name=n, bytes=s) for s, n in parts], named_by=named, json_evidence_copied=saved,
               evidence_directory=str(keep), why='Greg 2026-09-29: "Delete all 818 of bedrock. None of it is needed"',
               free_bytes_before=before, free_bytes_after=after, freed_bytes=after - before)
    with open(keep / 'bedrock-whole-receipt.json', 'x') as f:
        json.dump(out, f, sort_keys=True, indent=1)
        f.flush(); os.fsync(f.fileno())
    print(json.dumps({k: v for k, v in out.items() if k not in ('parts', 'named_by')}, sort_keys=True))
    sys.exit(0)

# ---- the retained copy (the receipt's own words and pins)
receipt = json.loads((root / 'calculations-receipt.json').read_bytes())
render = receipt.get('digest_render', {})
if receipt.get('status') != 'calculations_retained' or 'retained in the layer files' not in str(render.get('bedrock_tables')):
    raise SystemExit('the calculations receipt does not state the bedrock tables are retained in the layer files; nothing removed')
retained = []
def pin(path, nbytes, digest=None):
    p = Path(path)
    if not p.is_file() or p.stat().st_size != nbytes:
        raise SystemExit('retained copy missing or differs in size: %s' % path)
    if digest is not None and sha(p) != digest:
        raise SystemExit('retained copy differs in sha256: %s' % path)
    retained.append(dict(path=str(p), bytes=nbytes, sha256_checked=digest is not None))
for name, item in sorted(receipt['ledgers'].items()):
    pin(item['path'], item['bytes'])
pin(receipt['derivation']['path'], receipt['derivation']['bytes'], receipt['derivation']['sha256'])
pin(receipt['digest']['path'], receipt['digest']['bytes'])
pin(receipt['digest_proof']['path'], receipt['digest_proof']['bytes'], receipt['digest_proof']['sha256'])
pin(receipt['result']['path'], receipt['result']['bytes'])
pin(render['moved_aside']['digest'], render['previous_digest']['bytes'])
derive_text = Path(receipt['derivation']['path']).read_text(errors='replace')

# ---- targets
plan = []
for t in targets:
    if not any(re.fullmatch(p, t) for p in ALLOWED):
        raise SystemExit('target not of an allowed kind: %r' % t)
    base = derived / t
    if base.is_symlink() or not base.is_dir():
        raise SystemExit('no such directory (or a symlink): %s' % base)
    items = [base]
    m = re.fullmatch(r'(\.digest-[0-9a-f]{32})/table-(\d{4})', t)
    if m:
        if (derived / m.group(1) / ('table-%s.save.json' % m.group(2))).exists():
            raise SystemExit('%s was saved; refusing' % t)
        txt = derived / m.group(1) / ('table-%s.txt' % m.group(2))
        if txt.is_file():
            items.append(txt)
    if str(base) in derive_text:
        raise SystemExit('%s is named by the pinned derive.json; refusing' % t)
    plan.append((t, items))

# ---- references outside work/derived, open files, lock
paths = [str(i) for _, items in plan for i in items]
refs = []
for top in (BOX / 'work', BOX / 'receipts'):
    for base, dirs, files in os.walk(top):
        if base.startswith(str(derived)):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if not d.startswith('.digest') and d not in ('.projection-v2', '.rows')]
        for name in files:
            if not name.endswith('.json'):
                continue
            f = os.path.join(base, name)
            try:
                if os.path.getsize(f) > 64 << 20:
                    continue
                text = open(f, errors='replace').read()
            except OSError:
                continue
            for p in paths:
                if p in text:
                    refs.append((p, f))
if refs:
    raise SystemExit('targets named by retained files, nothing removed: %s' % json.dumps(refs[:10]))
open_files = []
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit():
        continue
    try:
        for fd in (proc / 'fd').iterdir():
            try:
                target = os.readlink(fd)
            except OSError:
                continue
            if any(target == p or target.startswith(p + '/') for p in paths):
                open_files.append((int(proc.name), target))
    except OSError:
        continue
if open_files:
    raise SystemExit('files in use, nothing removed: %s' % json.dumps(open_files[:10]))
lock = (root / 'calculation.lock').open('a')
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    raise SystemExit('the calculation root is locked: ROOT is running') from None

sizes = {t: sum(size(i) for i in items) for t, items in plan}
print('### retained copy (checked)')
for r in retained:
    print('  %14d  %s%s' % (r['bytes'], r['path'], '  (sha256 matched)' if r['sha256_checked'] else ''))
print('### targets')
for t, _ in plan:
    print('  %14d  %s' % (sizes[t], t))
print(json.dumps(dict(schema='FRANKIE_CLEANUP_BEDROCK_PLAN_V1', mode=mode, target_bytes=sum(sizes.values()),
                      targets=len(plan), free_bytes=free()), sort_keys=True))
if mode == 'plan':
    sys.exit(0)

before = free()
stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
keep = BOX / 'receipts' / ('bedrock-cleanup-%s' % stamp)
keep.mkdir(parents=True)
saved = 0
for t, items in plan:
    for item in items:
        if item.is_dir():
            for base, dirs, files in os.walk(item):
                for name in files:
                    f = Path(base) / name
                    if name.endswith('.json') and f.lstat().st_size <= 4 << 20:
                        dest = keep / f.relative_to(derived)
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(f, dest)
                        saved += 1
removed = []
for t, items in plan:
    for item in items:
        nbytes = size(item)
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
        removed.append(dict(path=str(item), bytes=nbytes))
        print('removed %14d  %s' % (nbytes, item))
after = free()
out = dict(schema='FRANKIE_CLEANUP_BEDROCK_V1', at=stamp, root=str(root), retained_copy=retained, removed=removed,
           removed_bytes=sum(r['bytes'] for r in removed), json_evidence_copied=saved, evidence_directory=str(keep),
           free_bytes_before=before, free_bytes_after=after, freed_bytes=after - before)
with open(keep / 'bedrock-cleanup-receipt.json', 'x') as f:
    json.dump(out, f, sort_keys=True, indent=1)
    f.flush(); os.fsync(f.fileno())
print(json.dumps({k: v for k, v in out.items() if k not in ('retained_copy', 'removed')}, sort_keys=True))
PY
