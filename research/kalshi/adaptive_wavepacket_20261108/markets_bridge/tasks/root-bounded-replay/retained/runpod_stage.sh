#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
base=/opt/frankie-box
ctl=$base/replay-control
markets=$base/replay-code/markets
producers=$base/producers
repo=https://github.com/DavisAI1974/Markets.git
root_pin=db96f24f3260bf0d70c763b297c2ba9b84f571a6
native_pin=2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134
tape_pin=1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202
mkdir -p "$base/replay-code" "$base/replay-tapes" "$base/work"
checkout() {
    local target=$1 pin=$2 patterns=$3
    if [ -f "$target/.git/replay-ready" ]; then
        return
    fi
    mkdir -p "$target"
    git -C "$target" init -q
    if ! git -C "$target" remote get-url origin >/dev/null 2>&1; then
        git -C "$target" remote add origin "$repo"
    fi
    git -C "$target" config remote.origin.promisor true
    git -C "$target" config remote.origin.partialclonefilter blob:none
    git -C "$target" -c protocol.version=2 fetch --depth=1 --filter=blob:none origin "$pin"
    git -C "$target" sparse-checkout set --no-cone --stdin < "$patterns"
    git -C "$target" checkout --detach "$pin"
    touch "$target/.git/replay-ready"
}
checkout "$markets" "$root_pin" "$ctl/markets-paths" &
market_pid=$!
checkout "$producers" "$native_pin" "$ctl/producers-paths" &
producer_pid=$!
for day in 20231002 20231003 20231017; do
    file="NG_v0_mbo_${day}.dbn.zst"
    curl --fail --silent --show-error --retry 4 --max-time 120         "https://raw.githubusercontent.com/DavisAI1974/Markets/$tape_pin/data/nymex_mbo/ng_v0_oct2023/$file"         -o "$base/replay-tapes/$file.pending" &
done
for job in $(jobs -pr); do wait "$job"; done
wait "$market_pid"
wait "$producer_pid"
cd "$markets"
for day in 20231002 20231003 20231017; do
    dest="research/kalshi/frankie_boss/blocks/BLOCK_${day}_SOURCE_MANIFEST.json"
    install -m 0644 "$ctl/BLOCK_${day}_SOURCE_MANIFEST.json" "$dest"
    git add -- "$dest"
done
git -c user.name='Replay Runner' -c user.email='replay@localhost'     -c commit.gpgsign=false commit -m 'Bind three reviewed Git tape scopes for this replay'
git rev-parse HEAD > "$ctl/runtime-commit"
test "$(git -C "$producers" rev-parse HEAD)" = "$native_pin"
python3 - "$ctl" "$base/replay-tapes" <<'PY'
import hashlib,json,sys
from pathlib import Path
control,tapes=map(Path,sys.argv[1:])
sources={x['member_key']:x for manifest in control.glob('BLOCK_*_SOURCE_MANIFEST.json') for x in json.loads(manifest.read_bytes())['sources']}
for name,x in sources.items():
    file=tapes/(name+'.pending')
    with file.open('rb') as f:
        observed=hashlib.file_digest(f,'sha256').hexdigest()
    if file.stat().st_size != x['size_bytes'] or observed != x['sha256']:
        raise ValueError(name)
    file.rename(tapes/name)
PY
python3 -m venv "$base/replay-code/venv"
py="$base/replay-code/venv/bin/python"
"$py" -m pip install --disable-pip-version-check --no-cache-dir   --extra-index-url https://download.pytorch.org/whl/cpu   -r deploy/aws/box/frankie_box_venv_requirements.txt
"$py" -m pip check
for adapter in research.kalshi.frankie_boss.operations.ingest_block_sources deploy/aws/box/frankie_box_experiment_root.py deploy/aws/box/frankie_box_experiment_teacher.py; do
    if [[ "$adapter" = *.py ]]; then "$py" "$adapter" --help >/dev/null; else "$py" -m "$adapter" --help >/dev/null; fi
done
touch "$ctl/ready"