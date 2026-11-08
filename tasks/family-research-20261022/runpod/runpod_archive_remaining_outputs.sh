#!/usr/bin/env bash
set -Eeuo pipefail
day=$1
case "$day" in 20231002|20231003|20231017) ;; *) exit 64 ;; esac
base=/opt/frankie-box
control=$base/replay-control/$day
root=$base/work/experiment-roots/ng-replay-$day
publication=$base/work/git-publication/$day
archive=$publication/root-native-remaining
mkdir -p "$publication"
exec 9>"$publication/root-native-remaining.lock"
flock -n 9
[[ ! -d "$archive" ]] || exit 0
read -r _ status < "$control/status"
[[ "$status" == producer-handoff-sealed ]]
pending=$(mktemp -d "$publication/root-native-remaining.partial.XXXXXX")

python3 - "$root" "$day" "$pending" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
day, pending = sys.argv[2], Path(sys.argv[3])
work = root / "work"
legacy = json.loads((work / "legacy-stage.json").read_bytes())
native = json.loads((work / "native-stage.json").read_bytes())
derived = json.loads((work / "derive.json").read_bytes())
compact = {
    "20231002": {"legacy_price", "legacy_native_signed_flow", "legacy_per_second_roll20",
                 "legacy_book_imbalance", "legacy_structure_observables"},
    "20231017": {"legacy_price", "legacy_native_signed_flow", "legacy_per_second_roll20"},
}.get(day, set())

files = {}
def add(path, expected_size=None, sha256=None):
    path = Path(path).resolve(strict=True)
    relative = path.relative_to(root).as_posix()
    size = path.stat().st_size
    if not path.is_file() or (expected_size is not None and expected_size != size):
        raise ValueError(f"sealed artifact differs: {path}")
    files[relative] = dict(bytes=size, sha256=sha256)

for item in legacy["artifacts"]:
    path = Path(item["path"])
    if item.get("kind") == "spool" and path.name != "frames.jsonl":
        add(path, item["bytes"], item.get("sha256"))
for item in native["artifacts"]:
    if Path(item["path"]).name != "receipt.json":
        add(item["path"], item["bytes"], item.get("sha256"))
for name, item in derived["layers"].items():
    if name not in compact and item.get("path"):
        add(item["path"], item.get("bytes"), item.get("sha256"))
for relative in ("source-binding.json", "calculation-pins.json", "work/native-layer-records.json"):
    add(root / relative)

(pending / "members.nul").write_bytes(b"".join(name.encode() + b"\0" for name in sorted(files)))
index = dict(day=day, source_root=str(root), files=files, reused_compact_root_tables=sorted(compact),
             separate_root_frames="work/derived/.rows/frames.jsonl", producer_revision="6f9178bbb97721c7a71e94bb602ac256db348c87")
(pending / "source.json").write_text(json.dumps(index, indent=2, sort_keys=True)+"\n", encoding="utf-8")
PY

tar -C "$root" --no-recursion --null -T "$pending/members.nul" -cf - \
    | nice -n 10 zstd -q --check --long=27 -2 -T2 -c \
    | split -b 64MiB -d -a 6 - "$pending/remaining.tar.zst.part-"
(
    cd "$pending"
    sha256sum remaining.tar.zst.part-* > SHA256SUMS
)
mv -T -- "$pending" "$archive"
