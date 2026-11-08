set -eu
base=/home/greg/ng-root-bounded-13eb0f6ab
work="$base/btrfs-canary.EEJX06"
out=/mnt/e/tmp/ng-root-bounded-13eb0f6ab/compression
test -s "$out/btrfs-usage.txt"
mount -o ro,loop -- "$work/only-scratch.img" "$work/mount"
trap 'umount -- "$work/mount"' EXIT
python3 - "$base" "$work" > "$out/btrfs-offsets.json" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

base, work = map(Path, sys.argv[1:])
relative = 'work/derived/.rows/frames.jsonl'
ext4 = base / 'out/02-healthy' / relative
btrfs = work / 'mount/btrfs-resume' / relative
expected = {0, 100, 257, 511, 777, 1023, 1302}
checked = []
with ext4.open('rb') as raw, btrfs.open('rb') as transparent:
    for row in range(max(expected) + 1):
        offset = raw.tell()
        data = raw.readline()
        if row not in expected:
            continue
        if not data.endswith(b'\n'):
            raise ValueError(f'Raw row incomplete at {row}')
        transparent.seek(offset)
        observed = transparent.read(len(data))
        if observed != data:
            raise ValueError(f'Row {row} differs at logical offset {offset}')
        checked.append(dict(row=row, offset=offset, length=len(data), sha256=hashlib.sha256(data).hexdigest()))
    if raw.read(1) or transparent.read(1):
        raise ValueError('Unexpected trailing frame')
print(json.dumps(checked, indent=2))
PY