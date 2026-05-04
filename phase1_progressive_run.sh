#!/bin/bash
# Progressive Phase 1 driver:
# - Collects 4 hours of Coinbase BTC-USD WS data in the background
# - At checkpoints (15 min, 1 hr, 2 hr, 3 hr, 4 hr), runs analysis on the
#   cumulative bins seen so far and saves a per-checkpoint report + plot.
#
# Each later checkpoint is a SUPERSET of earlier ones (cumulative).
# Off-ramps: kill the collection PID at any point; intermediate reports
# remain valid and complete for whatever duration was collected.

set -u
cd "$(dirname "$0")"

DURATION_S=${1:-14400}              # default 4 hours; override for testing
PREFIX=${PREFIX:-phase1}            # file prefix; allows multiple concurrent/sequential runs
BINS_PATH=${BINS_PATH:-${PREFIX}_bins.json}
LOGDIR=${LOGDIR:-${PREFIX}_logs}
mkdir -p "$LOGDIR"

START_T=$(date +%s)
echo "[progressive] start $(date) duration=${DURATION_S}s bins=$BINS_PATH" | tee -a "$LOGDIR/orchestrator.log"

# Spawn collection in background
python coinbase_btcusd_4hr_trajectory.py \
    --collect-only \
    --duration "$DURATION_S" \
    --bins-path "$BINS_PATH" \
    > "$LOGDIR/collect.log" 2>&1 &
COLLECT_PID=$!
echo "[progressive] collection PID=$COLLECT_PID" | tee -a "$LOGDIR/orchestrator.log"

wait_until_t() {
    local target=$1
    while :; do
        local now=$(date +%s)
        local elapsed=$((now - START_T))
        if [ "$elapsed" -ge "$target" ]; then break; fi
        # Don't oversleep past the target
        local remain=$((target - elapsed))
        sleep $((remain < 30 ? remain : 30))
    done
}

run_checkpoint() {
    local label=$1
    local offset=$2
    if [ "$DURATION_S" -lt "$offset" ]; then
        echo "[progressive] skip $label (DURATION_S<$offset)" | tee -a "$LOGDIR/orchestrator.log"
        return
    fi
    wait_until_t "$offset"
    if [ ! -s "$BINS_PATH" ]; then
        echo "[progressive] $label: no bins yet at $BINS_PATH; skipping" | tee -a "$LOGDIR/orchestrator.log"
        return
    fi
    echo "[progressive] $label checkpoint at $(date) (elapsed=$(($(date +%s) - START_T))s)" | tee -a "$LOGDIR/orchestrator.log"
    python coinbase_btcusd_4hr_trajectory.py \
        --from-bins \
        --bins-path "$BINS_PATH" \
        --report-path "${PREFIX}_report_${label}.json" \
        --plot-path "${PREFIX}_trajectory_${label}.png" \
        > "$LOGDIR/checkpoint_${label}.log" 2>&1
    echo "[progressive] $label done; report=${PREFIX}_report_${label}.json" | tee -a "$LOGDIR/orchestrator.log"
}

run_checkpoint "15min"  900
run_checkpoint "1hr"    3600
run_checkpoint "2hr"    7200
run_checkpoint "3hr"   10800
run_checkpoint "4hr"   14400

# Wait for collection to finish if we're below the 4hr checkpoint
wait "$COLLECT_PID" 2>/dev/null || true

echo "[progressive] complete $(date)" | tee -a "$LOGDIR/orchestrator.log"
