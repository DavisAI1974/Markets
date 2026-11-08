#!/usr/bin/env bash
set -Eeuo pipefail
day=$1
case "$day" in 20231002|20231003|20231017) ;; *) exit 64 ;; esac
base=/opt/frankie-box
ctl=$base/replay-control
logs=$ctl/$day
bundle=$ctl/standalone-f06e8e90f
runner=$ctl/runpod_replay_discovery_compat.sh
bootstrap=$ctl/runpod_root_bootstrap.py
exec 8>"$logs/native-compat-recovery.lock"
flock -n 8

while read -r _ state < "$logs/status"; do
    case "$state" in
        producer-handoff-sealed) exit 0 ;;
        failed\ *) break ;;
    esac
    sleep 10
done
[[ "$state" == 'failed root-native exit=1' ]]
grep -qF "SharedMemory.__init__() got an unexpected keyword argument 'track'" "$logs/root.log"
flock -w 60 "$logs/job.lock" -c true
flock -w 60 "$logs/standalone.lock" -c true
cp --update=none "$logs/root.log" "$logs/root.python312.log"
export FRANKIE_REPLAY_PYTHON=/opt/replay-runtime/venv/bin/python
export FRANKIE_REPLAY_BOOTSTRAP="$bootstrap"
nohup bash "$runner" "$day" --after-ingest >> "$logs/native-compat-producer.log" 2>&1 < /dev/null &
producer=$!
for ((attempt=0; attempt<15; attempt++)); do
    read -r _ state < "$logs/status"
    case "$state" in waiting-for-runtime|preflight|root-native|producer-handoff-sealed) break ;; esac
    kill -0 "$producer"
    sleep 1
done
case "$state" in waiting-for-runtime|preflight|root-native|producer-handoff-sealed) ;; *) exit 1 ;; esac
nohup bash "$bundle/tasks/family-research-20261022/runpod/runpod_standalone_after_handoff.sh" \
    "$day" "$bundle" >> "$logs/standalone.log" 2>&1 < /dev/null &
printf 'Recovery producer %s and standalone waiter %s\n' "$producer" "$!"
