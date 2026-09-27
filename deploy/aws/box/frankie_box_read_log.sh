# Read-only: print part of one file under /opt/frankie-box (logs, receipts, session out). Inputs: FILE (path under
# /opt/frankie-box, e.g. logs/producer-tests.log), MODE (tail | head | grep), LINES (default 120), PATTERN (grep
# mode: an extended regex; prints matches with 3 lines of context). MODE=receipt prints the full JSON receipt
# with its actual byte hash for the next manual stage. Refuses paths outside /opt/frankie-box.
set -u
ROOT=/opt/frankie-box
FILE="${FILE:-logs/producer-tests.log}"; MODE="${MODE:-tail}"; LINES="${LINES:-120}"; PATTERN="${PATTERN:-}"
case "$FILE" in *..*|/*) echo "FILE must be relative to $ROOT without .."; exit 2;; esac
P="$ROOT/$FILE"
# Locate immutable recovery generations so subsequent receipt reads use observed paths.
if [ "$MODE" = generations ]; then
  /opt/frankie-box/venv/bin/python -I -S -B - "$P" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1]).resolve(strict=True)
allowed = pathlib.Path('/opt/frankie-box/work/monday-calculations').resolve(strict=True)
if not root.is_relative_to(allowed) or root.name != 'bedrock' or root.parent.name != 'work':
    raise SystemExit('existing Monday bedrock directory required')
items = []
for path in sorted(root.glob('recovery-*')):
    if path.is_dir() and not path.is_symlink():
        checkpoints = sorted((path / 'checkpoints').glob('checkpoint-[0-9][0-9][0-9][0-9][0-9][0-9].json'))
        items.append(dict(path=str(path), latest_checkpoint=str(checkpoints[-1]) if checkpoints else None,
                          receipts=[name for name in ('reconstruction-receipt.json', 'parallel-transition-receipt.json', 'runtime-workers-receipt.json')
                                    if (path / name).is_file()]))
print(json.dumps(dict(recovery_generations=items), sort_keys=True))
PY
  exit $?
fi
# Read actual compressed-projection receipts and sizes without scanning payloads.
if [ "$MODE" = projection ]; then
  /opt/frankie-box/venv/bin/python -I -S -B - "$P" <<'PY'
import hashlib,json,os,pathlib,sys,time
root=pathlib.Path(sys.argv[1]).resolve(strict=True)
allowed=pathlib.Path('/opt/frankie-box/work/monday-calculations').resolve(strict=True)
if not root.is_relative_to(allowed) or root.name!='.projection-v2':
    raise SystemExit('existing compressed projection root required')
def read(path):
    raw=path.read_bytes()
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()),json.loads(raw)
plan_pin,plan=read(root/'plan.json')
workers=sorted(root.glob('workers-*.json'),key=lambda p:p.stat().st_mtime_ns)
result=dict(at=time.time(),plan=plan_pin,workers=read(workers[-1]) if workers else None,kinds={})
for kind in ('member','lifecycle'):
    files=sorted((root/kind).glob('range-*.json'))
    archives=list((root/kind).glob('*.blocks'))
    item=dict(completed_ranges=len(files),archive_files=len(archives),
              archive_bytes=sum(p.stat().st_size for p in archives),first=None,last=None)
    for key,path in [('first',files[0]),('last',files[-1])] if files else []:
        pin,value=read(path)
        item[key]=dict(pin=pin,binding=value['binding'],actual_start=value['actual_start'],
                       actual_end=value['actual_end'],rows=value['rows'],archive=value['archive'],
                       worker=value['worker'],readback_verified=value['readback_verified'])
    result['kinds'][kind]=item
stat=os.statvfs(root)
result['free_bytes']=stat.f_bavail*stat.f_frsize
print(json.dumps(result,sort_keys=True))
PY
  exit $?
fi
# Metadata-only storage inventory for the retained Monday calculation root.
if [ "$MODE" = storage ]; then
  /opt/frankie-box/venv/bin/python -I -S -B - "$P" <<'PY'
import collections, heapq, json, os, pathlib, stat, sys, time
root = pathlib.Path(sys.argv[1]).resolve(strict=True)
allowed = pathlib.Path('/opt/frankie-box/work/monday-calculations').resolve(strict=True)
if root.parent != allowed or not root.is_dir():
    raise SystemExit('one existing Monday calculation root required')
seen, groups, largest, errors = set(), {}, [], []
files, logical, allocated, hardlinks = 0, 0, 0, 0
for parent, directories, names in os.walk(root, followlinks=False):
    directories[:] = [n for n in directories if not pathlib.Path(parent, n).is_symlink()]
    for name in names:
        path = pathlib.Path(parent, name)
        try:
            info = path.lstat()
        except OSError as error:
            errors.append(dict(path=str(path.relative_to(root)), error=type(error).__name__))
            continue
        if not stat.S_ISREG(info.st_mode):
            continue
        relative = str(path.relative_to(root))
        key = (info.st_dev, info.st_ino)
        if key in seen:
            hardlinks += 1
            continue
        seen.add(key)
        files += 1
        logical += info.st_size
        size = info.st_blocks * 512
        allocated += size
        parts = pathlib.Path(relative).parts
        group = '/'.join(parts[:3] if len(parts) > 3 else parts[:-1]) or '.'
        row = groups.setdefault(group, dict(files=0, bytes=0, allocated_bytes=0))
        row['files'] += 1
        row['bytes'] += info.st_size
        row['allocated_bytes'] += size
        item = (size, relative, info.st_size, info.st_mtime_ns, info.st_nlink)
        if len(largest) < 25:
            heapq.heappush(largest, item)
        elif item > largest[0]:
            heapq.heapreplace(largest, item)
statv = os.statvfs(root)
print(json.dumps(dict(schema='FRANKIE_CALCULATION_STORAGE_INVENTORY_V1',
    at=time.time(), root=str(root), files=files, unique_inode_bytes=logical,
    allocated_bytes=allocated, duplicate_hardlink_names=hardlinks,
    filesystem_bytes=statv.f_blocks*statv.f_frsize,
    available_bytes=statv.f_bavail*statv.f_frsize,
    free_including_reserved_bytes=statv.f_bfree*statv.f_frsize,
    largest_groups=[dict(path=k, **v) for k,v in sorted(groups.items(),
        key=lambda item:item[1]['allocated_bytes'], reverse=True)[:20]],
    largest_files=[dict(path=p, allocated_bytes=a, bytes=b, mtime_ns=m, links=n)
        for a,p,b,m,n in sorted(largest, reverse=True)],
    read_errors=errors[:10], read_error_count=len(errors),
    limitation='Live metadata inventory only; not a deletion authorization or a proof of redundant contents.'),
    sort_keys=True))
PY
  exit $?
fi
[ -f "$P" ] || { echo "no such file: $P"; ls -la "$(dirname "$P")" 2>/dev/null; exit 2; }
# Summarize an already-retained speedscope profile; never attach to a process.
if [ "$MODE" = profile ]; then
  /opt/frankie-box/venv/bin/python -I -S -B - "$P" <<'PY'
import collections, hashlib, json, pathlib, sys
path = pathlib.Path(sys.argv[1]).resolve(strict=True)
allowed = pathlib.Path('/opt/frankie-box/work/monday-calculations').resolve(strict=True)
if (not path.is_relative_to(allowed) or path.parent.parent.name != 'performance'
        or not (path.name.startswith('pid-') or path.name == 'profile-receipt.json')):
    raise SystemExit('retained Monday process profile required')
raw = path.read_bytes()
data = json.loads(raw)
if path.name == 'profile-receipt.json':
    if data.get('schema') != 'FRANKIE_NATIVE_LIVE_PROFILE_V1':
        raise SystemExit('retained native profile receipt required')
    def compact(rows, count):
        return [dict(file=pathlib.Path(row['frame'].get('file', '')).name,
                     function=row['frame'].get('name'), line=row['frame'].get('line'),
                     percent=row['percent'], weight=row['weight']) for row in rows[:count]]
    print(json.dumps(dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
        at=data['at'], seconds=data['seconds'], progress=data['progress'],
        total_cpu_seconds=sum(p['cpu_ticks_delta'] for p in data['profiles'])/data['clock_ticks'],
        profiles=[dict(pid=p['pid'], path=p['path'], sha256=p['sha256'],
            cpu_seconds=p['cpu_ticks_delta']/data['clock_ticks'], active_weight=p['total_weight'],
            leaf=compact(p['leaf'], 10 if i == 0 else 3),
            inclusive=compact(p['inclusive'], 10 if i == 0 else 3))
            for i,p in enumerate(data['profiles'])],
        limitations=data['limitations']), sort_keys=True))
    raise SystemExit(0)
frames = data['shared']['frames']
paths = collections.Counter()
total = 0.0
for profile in data['profiles']:
    for stack, weight in zip(profile['samples'], profile.get('weights', [1] * len(profile['samples']))):
        if not stack:
            continue
        total += weight
        leaf = frames[stack[-1]]
        if 'cloudpickle' in leaf.get('file', '') and leaf.get('name') == 'dump':
            callers = tuple((pathlib.Path(frames[i].get('file', '')).name, frames[i].get('name'), frames[i].get('line'))
                            for i in stack if pathlib.Path(frames[i].get('file', '')).name in
                            ('frankie_box_native_auxiliary.py', 'frankie_box_parallel_evidence.py',
                             'frankie_box_native_parallel.py') and frames[i].get('name') != 'consume_after_reconstruction')
            paths[callers] += weight
print(json.dumps(dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
    total_active_weight=total, serialization_leaf_weight=sum(paths.values()),
    send_paths=[dict(callers=[dict(file=f, name=n, line=l) for f,n,l in callers],
                     weight=weight, percent_active=100*weight/total)
                for callers,weight in paths.most_common()],
    limitations=['Retained nonblocking Python samples; not wall-clock shares or a speedup measurement']),
    sort_keys=True, indent=2))
PY
  exit $?
fi
if [ "$MODE" = receipt ]; then
  case "$FILE" in */authorship-receipt.json|*/preparation-receipt.json|*/publication-receipt.json|*/calculations-receipt.json|*/reconstruction-receipt.json|*/parallel-transition-receipt.json|*/runtime-workers-receipt.json|*/pause-for-parallel-[0-9]*.json|*/pause-for-native-workers-[0-9]*.json|*/checkpoints/checkpoint-[0-9][0-9][0-9][0-9][0-9][0-9].json|*/checkpoints/controller-state-[0-9][0-9][0-9][0-9][0-9][0-9].json) ;;
    *) echo "receipt mode requires a pipeline or checkpoint receipt"; exit 2;; esac
  /opt/frankie-box/venv/bin/python -B - "$P" <<'PY'
import hashlib, json, pathlib, sys
path = pathlib.Path(sys.argv[1])
raw = path.read_bytes()
value = json.loads(raw)
print('FILE_PIN ' + json.dumps(dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()), sort_keys=True))
print(json.dumps(value, sort_keys=True, indent=2))
PY
  exit $?
fi
echo "### $P ($(wc -c < "$P") bytes, $(wc -l < "$P") lines, $MODE $LINES)"
case "$MODE" in
  tail) tail -n "$LINES" "$P" ;;
  head) head -n "$LINES" "$P" ;;
  grep) [ -n "$PATTERN" ] || { echo "PATTERN required"; exit 2; }; grep -nE -C 3 -- "$PATTERN" "$P" | head -n "$LINES" ;;
  *) echo "MODE must be tail, head or grep"; exit 2 ;;
esac | cut -c1-400
