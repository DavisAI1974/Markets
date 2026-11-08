#!/usr/bin/env bash
set -Eeuo pipefail
day=$1
parent=$2
child=$3
base=/opt/frankie-box
ctl=$base/replay-control
case "$day" in 20231002|20231003|20231017) ;; *) exit 64 ;; esac
[[ "$parent" =~ ^[0-9]+$ && "$child" =~ ^[0-9]+$ ]]
original="bash $ctl/runpod_replay_day.sh $day"
[[ $(tr '\000' ' ' < "/proc/$parent/cmdline") == "$original " ]]
[[ $(ps -o ppid= -p "$child" | tr -d ' ') == "$parent" ]]
args=$(tr '\000' ' ' < "/proc/$child/cmdline")
[[ "$args" == *"operations.ingest_block_sources --manifest "*"BLOCK_${day}_SOURCE_MANIFEST.json "* ]]
read -r _ stage < "$ctl/$day/status"
[[ "$stage" == ingest ]]
# Pause only the shell waiting for ingest. Its Python child and encoder or
# conformance workers continue under the original lock.
kill -STOP "$parent"
trap 'kill -CONT "$parent" 2>/dev/null || :' EXIT
[[ $(ps -o stat= -p "$parent") == T* ]]
while kill -0 "$child" 2>/dev/null; do
    [[ $(ps -o stat= -p "$child") != Z* ]] || break
    sleep 5
done
test -s "$base/work/ingest-ng-replay-$day/ingestion-receipt.json"
# Ingest is finished. Replace its waiting shell before it can start ROOT or
# the old teacher route. The new runner acquires the same day lock.
kill -KILL "$parent"
trap - EXIT
exec bash "$ctl/runpod_replay_discovery.sh" "$day" --after-ingest
