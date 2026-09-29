# The teacher-only step (frankie_box_experiment_teacher.py): the Dipole teacher's rows for each listed day, each day its
# own walk on its own sealed journal, the days side by side, each under taskset on its own share of the CPUs (never one
# walk across days: that would carry one day's state into the next). Inputs: CODE_ROOT (staged checkout), DAYS (comma
# list YYYYMMDD), INGESTION_RECEIPTS (comma list, same order: each day's ingestion-receipt.json under
# /opt/frankie-box/work/ingest-*/). Output per day: /opt/frankie-box/work/experiment-teacher-rows/<day>/. A day whose rows
# exist declines; a day that fails is listed and the others go on. A probe:
# frankie_box_progress.sh DIRECTORY=/opt/frankie-box/work/experiment-teacher-rows/<day>. No model, no Pod, no Granite.
set -u
: "${MARKETS_SHA:?full dispatched commit required}"; : "${CODE_ROOT:?staged clean checkout required}"
: "${DAYS:?comma list of days required}"; : "${INGESTION_RECEIPTS:?comma list of ingestion receipts required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
case "$DAYS$INGESTION_RECEIPTS" in *..*) echo "no .. in DAYS or INGESTION_RECEIPTS" >&2; exit 2;; esac
ND=$(echo "$DAYS" | tr ',' '\n' | grep -c .); NR=$(echo "$INGESTION_RECEIPTS" | tr ',' '\n' | grep -c .)
[ "$ND" -ge 1 ] && [ "$ND" = "$NR" ] || { echo "DAYS and INGESTION_RECEIPTS must be equal-length comma lists" >&2; exit 2; }
NCPU=$(nproc); SHARE=$((NCPU / ND)); [ "$SHARE" -ge 2 ] || SHARE=2
LOGS=/opt/frankie-box/work/experiment-teacher-rows/logs; mkdir -p "$LOGS"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
I=0; PIDS=""
for DAY in $(echo "$DAYS" | tr ',' ' '); do
  I=$((I + 1)); R=$(echo "$INGESTION_RECEIPTS" | cut -d, -f"$I")
  case "$DAY" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) echo "bad day $DAY" >&2; exit 2;; esac
  case "$R" in /opt/frankie-box/work/ingest-*/ingestion-receipt.json) ;; *) echo "bad receipt $R" >&2; exit 2;; esac
  [ -s "$R" ] || { echo "no receipt at $R" >&2; exit 2; }
  FIRST=$(( (I - 1) * SHARE )); LAST=$(( FIRST + SHARE - 1 )); [ "$LAST" -lt "$NCPU" ] || LAST=$((NCPU - 1))
  SHA=$(sha256sum "$R" | cut -d' ' -f1)
  LOG="$LOGS/$DAY-$(date +%s).log"
  echo "### $DAY: CPUs $FIRST-$LAST, receipt $R ($SHA), log $LOG"
  taskset -c "$FIRST-$LAST" /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_experiment_teacher.py" \
    --day "$DAY" --ingestion-receipt "$R" --ingestion-receipt-sha256 "$SHA" --workers $((SHARE - 1)) > "$LOG" 2>&1 &
  PIDS="$PIDS $!:$DAY:$LOG"
done
FAILED=0
for P in $PIDS; do
  PID=${P%%:*}; REST=${P#*:}; DAY=${REST%%:*}; LOG=${REST#*:}
  if wait "$PID"; then echo "### $DAY done"; else echo "### $DAY FAILED (listed; the other days go on)"; FAILED=$((FAILED + 1)); fi
  tail -n 40 "$LOG"
done
[ "$FAILED" -eq 0 ] || exit 3
