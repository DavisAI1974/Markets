#!/usr/bin/env bash
set -Eeuo pipefail
day=$1
case "$day" in 20231002|20231003|20231017) ;; *) exit 64 ;; esac

base=/opt/frankie-box
root=$base/work/experiment-roots/ng-replay-$day
source=$root/work/derived/.rows/frames.jsonl
stage=$root/work/legacy-stage.json
publication=$base/work/git-publication/$day
archive=$publication/root-frames
mkdir -p "$publication"
exec 9>"$publication/root-frames.lock"
flock -n 9
[[ ! -d "$archive" ]] || exit 0

pending=$(mktemp -d "$publication/root-frames.partial.XXXXXX")
python3 - "$source" "$stage" "$pending/source.json" <<'PY'
import json
import sys
from pathlib import Path

source, stage, index = map(Path, sys.argv[1:])
artifacts = json.loads(stage.read_bytes())["artifacts"]
artifact, = [item for item in artifacts if item.get("path") == str(source)]
if artifact.get("kind") != "spool" or source.stat().st_size != artifact["bytes"]:
    raise ValueError("the ROOT frame spool differs from the finalized source")
index.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

fingerprint=$(stat -c '%d:%i:%s:%y' "$source")
nice -n 10 zstd -q --check --long=27 -2 -T2 -c -- "$source" \
    | split -b 64MiB -d -a 6 - "$pending/frames.jsonl.zst.part-"
[[ $(stat -c '%d:%i:%s:%y' "$source") == "$fingerprint" ]]
(
    cd "$pending"
    sha256sum frames.jsonl.zst.part-* > SHA256SUMS
)
mv -T -- "$pending" "$archive"
