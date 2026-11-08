#!/usr/bin/env bash
set -Eeuo pipefail
day=$1
after_ingest=${2:-}
[[ -z "$after_ingest" || "$after_ingest" == --after-ingest ]] || exit 64
case "$day" in 20231002|20231003|20231017) ;; *) exit 64 ;; esac
base=/opt/frankie-box
ctl=$base/replay-control
markets=$base/replay-code/markets
py=${FRANKIE_REPLAY_PYTHON:-$base/replay-code/venv/bin/python}
logs=$ctl/$day
mkdir -p "$logs"
exec 9>"$logs/job.lock"
flock -w 30 9
if [[ -f "$logs/status" ]]; then
    read -r _ retained_status < "$logs/status"
    [[ "$retained_status" != producer-handoff-sealed ]] || exit 0
fi
stage=waiting-for-runtime
mark() {
    printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" > "$logs/status.pending"
    mv -f "$logs/status.pending" "$logs/status"
    cat "$logs/status"
}
trap 'rc=$?; mark "failed $stage exit=$rc"; exit "$rc"' ERR
mark "$stage"
for ((attempt=0; attempt<900; attempt++)); do
    [[ -f "$ctl/ready" ]] && break
    sleep 2
done
test -f "$ctl/ready"
stage=preflight
mark "$stage"
"$py" - <<'PY'
import os
from pathlib import Path
cpus=sorted(os.sched_getaffinity(0))
cores={(Path(f'/sys/devices/system/cpu/cpu{cpu}/topology/physical_package_id').read_text().strip(),
        Path(f'/sys/devices/system/cpu/cpu{cpu}/topology/core_id').read_text().strip()) for cpu in cpus}
print('logical CPUs',len(cpus),'distinct cores',len(cores),flush=True)
if len(cpus)<32 or len(cores)<16:
    raise RuntimeError('insufficient physical cores for ROOT and Native overlap')
PY
df -BG "$base"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 FRANKIE_ROOT_NATIVE_OVERLAP=on
export FRANKIE_ROOT_LEGACY_FRAME_SHARDS=on FRANKIE_ROOT_LAYER_SPOOLS=reference
export FRANKIE_ROOT_DISK_FLOOR_GB=64 FRANKIE_TEACHER_CHANGES=1
cd "$markets"
export PYTHONPATH="$markets:$base/producers"
ingest=$base/work/ingest-ng-replay-$day
root=$base/work/experiment-roots/ng-replay-$day
receipt=$ingest/ingestion-receipt.json
manifest=research/kalshi/frankie_boss/blocks/BLOCK_${day}_SOURCE_MANIFEST.json
if [[ ! -f "$receipt" ]]; then
    stage=ingest
    mark "$stage"
    [[ -z "$after_ingest" ]]
    opening=()
    prior=$base/work/ingest-ng-replay-20231002/ingestion-receipt.json
    if [[ "$day" == 20231003 && -f "$prior" ]]; then
        opening=(--opening-receipt "$prior")
    fi
    "$py" -u -m research.kalshi.frankie_boss.operations.ingest_block_sources \
      --manifest "$manifest" --sources-dir "$base/replay-tapes" --output-dir "$ingest" \
      --session-policy cme_trading_day --writer compact --mode sequential --observation full \
      --verify deferred --workers 15 "${opening[@]}" > "$logs/ingest.log" 2>&1
fi
read -r receipt_sha _ < <(sha256sum "$receipt")
commit=$(cat "$ctl/runtime-commit")
policy=FRANKIE_SHARED_MARKET_TIMELINE_V1
stage=root-native
mark "$stage"
resume=()
if [[ -d "$root" ]]; then resume=(--resume); fi
root_command=("$py" -u)
if [[ -n ${FRANKIE_REPLAY_BOOTSTRAP:-} ]]; then root_command+=("$FRANKIE_REPLAY_BOOTSTRAP"); fi
"${root_command[@]}" deploy/aws/box/frankie_box_experiment_root.py \
  --commit "$commit" --ingestion-receipt "$receipt" --ingestion-receipt-sha256 "$receipt_sha" \
  --day "$day" --day-role discovery --output-root "$root" --data-workers 31 \
  --digest off --bedrock on --shared-market-policy "$policy" "${resume[@]}" > "$logs/root.log" 2>&1
mark "producer-handoff-sealed"
