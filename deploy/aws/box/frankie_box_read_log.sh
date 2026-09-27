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
[ -f "$P" ] || { echo "no such file: $P"; ls -la "$(dirname "$P")" 2>/dev/null; exit 2; }
# Summarize an already-retained speedscope profile; never attach to a process.
if [ "$MODE" = profile ]; then
  /opt/frankie-box/venv/bin/python -I -S -B - "$P" <<'PY'
import collections, hashlib, json, pathlib, sys
path = pathlib.Path(sys.argv[1]).resolve(strict=True)
allowed = pathlib.Path('/opt/frankie-box/work/monday-calculations').resolve(strict=True)
if not path.is_relative_to(allowed) or path.parent.parent.name != 'performance' or not path.name.startswith('pid-'):
    raise SystemExit('retained Monday process profile required')
raw = path.read_bytes()
data = json.loads(raw)
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
