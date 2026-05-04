#!/bin/bash
# Watches the phase1 orchestrator log for "X done" events and triggers
# matching Kraken analysis with the same label. Cross-venue per-checkpoint.
#
# Output: kraken_report_<label>.json, kraken_trajectory_<label>.png

set -u
cd "$(dirname "$0")"

mkdir -p kraken_logs
WATCHER_LOG=kraken_logs/checkpoint_watcher.log
ORCH_LOG=phase1_logs/orchestrator.log

echo "[kraken-watcher] starting at $(date -u)" | tee -a "$WATCHER_LOG"

# Tail orchestrator log; on each [progressive] X done; line, run kraken analysis
tail -F "$ORCH_LOG" 2>&1 | while IFS= read -r line; do
    if [[ "$line" =~ ^\[progressive\]\ ([a-z0-9]+)\ done\; ]]; then
        label="${BASH_REMATCH[1]}"
        echo "[kraken-watcher] triggering kraken analysis for $label at $(date -u)" \
            | tee -a "$WATCHER_LOG"
        python coinbase_btcusd_4hr_trajectory.py \
            --from-bins \
            --bins-path kraken_bins.json \
            --report-path "kraken_report_${label}.json" \
            --plot-path "kraken_trajectory_${label}.png" \
            > "kraken_logs/checkpoint_${label}.log" 2>&1
        echo "[kraken-watcher] $label done; report=kraken_report_${label}.json" \
            | tee -a "$WATCHER_LOG"
    fi
done
