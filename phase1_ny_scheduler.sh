#!/bin/bash
# Wait until target UTC time, then launch the progressive run with PREFIX=phase1_ny.
# Captures the NY trading-session window: NY open at ~14:00 UTC peak,
# NY lunch lull at 15:45-17:30 UTC, NY afternoon resume + pre-close.

set -u
cd "$(dirname "$0")"

TARGET_UTC=${1:-"2026-05-04 14:00:00"}
DURATION_S=${2:-14400}

TARGET_EPOCH=$(date -u -d "$TARGET_UTC" +%s)
NOW_EPOCH=$(date -u +%s)

mkdir -p phase1_ny_logs
LOG=phase1_ny_logs/scheduler.log

if [ "$NOW_EPOCH" -ge "$TARGET_EPOCH" ]; then
    echo "[scheduler] target $TARGET_UTC already passed; launching immediately" | tee -a "$LOG"
else
    delay=$((TARGET_EPOCH - NOW_EPOCH))
    echo "[scheduler] waiting ${delay}s until $TARGET_UTC UTC" | tee -a "$LOG"
    while [ $(date -u +%s) -lt "$TARGET_EPOCH" ]; do
        sleep 60
    done
fi

echo "[scheduler] launching phase1_progressive_run.sh with PREFIX=phase1_ny at $(date -u)" | tee -a "$LOG"
PREFIX=phase1_ny bash phase1_progressive_run.sh "$DURATION_S"
