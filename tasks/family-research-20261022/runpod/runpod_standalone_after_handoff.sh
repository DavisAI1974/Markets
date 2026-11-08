#!/usr/bin/env bash
set -Eeuo pipefail
day=$1
bundle=$2
case "$day" in 20231002|20231003|20231017) ;; *) exit 64 ;; esac
base=/opt/frankie-box
logs=$base/replay-control/$day
output=$base/work/standalone-inputs/$day
exec 9>"$logs/standalone.lock"
flock -n 9
mark() {
    printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" > "$logs/standalone-status.pending"
    mv -f "$logs/standalone-status.pending" "$logs/standalone-status"
}
stage=waiting-for-producers
trap 'rc=$?; mark "failed $stage exit=$rc"; exit "$rc"' ERR
mark "$stage"
while read -r _ producer_status < "$logs/status"; do
    case "$producer_status" in
        producer-handoff-sealed) break ;;
        failed\ *) mark "held $producer_status"; exit 1 ;;
    esac
    sleep 30
done
test "$producer_status" = producer-handoff-sealed
stage=standalone-inputs
mark "$stage"
cd "$bundle"
export PYTHONDONTWRITEBYTECODE=1
export NG_REPLAY_PINNED_SOURCES="$bundle/pins"
export NG_REPLAY_TAPE_DIR="$base/replay-tapes"
/opt/replay-runtime/venv/bin/python -B -u \
    -m research.kalshi.adaptive_wavepacket_20261108.markets_bridge.october18_inputs \
    --day "$day" --output-dir "$output"
mark "standalone-inputs-sealed"
