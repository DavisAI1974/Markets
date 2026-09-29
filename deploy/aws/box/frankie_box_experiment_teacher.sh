# The teacher-only step (frankie_box_experiment_teacher.py): the Dipole teacher's rows for each listed day, each day its
# own walk on its own sealed journal, the days side by side, each under taskset on its own share of the CPUs (never one
# walk across days: that would carry one day's state into the next). Inputs: CODE_ROOT (staged checkout), DAYS (comma
# list YYYYMMDD), INGESTION_RECEIPTS (comma list, same order: each day's ingestion-receipt.json under
# /opt/frankie-box/work/ingest-*/). Output per day: /opt/frankie-box/work/experiment-teacher-rows/<day>/. A day whose rows
# exist declines; a day that fails is listed and the others go on. A probe:
# frankie_box_progress.sh DIRECTORY=/opt/frankie-box/work/experiment-teacher-rows/<day>. No model, no Pod, no Granite.
# Frankie's historical data points: optional DAY_EXTERNALS + DAY_EXTERNAL_SHA256S (comma lists, same order as DAYS, given
# together); without them each day's file is taken from beside its sealed ingest (its day-external-receipt.json sha256).
# The BOSS teacher's external section is written to <day>/external-section/.
# CPU budget (Greg, 2026-09-29: "add the cpu budget to teacher"): optional CPUS = how many of the box's cores the
# teacher may use (default all of them, as before), split between the days and pinned from core 0; the cores left over
# stay free for the ingests and other steps running beside it.
# CPU booking (Greg, 2026-09-29: "Correct 16 and no double booking"): the cores are THIS PROCESS'S OWN affinity, never the
# box's absolute 0..N-1. The orchestrator starts this step under taskset -c <its booked 16> (frankie_box_cores.py), so
# every day's taskset is a slice of the booking; started by hand with the box's whole affinity it is exactly as before.
set -u
: "${MARKETS_SHA:?full dispatched commit required}"; : "${CODE_ROOT:?staged clean checkout required}"
: "${DAYS:?comma list of days required}"; : "${INGESTION_RECEIPTS:?comma list of ingestion receipts required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
case "$DAYS$INGESTION_RECEIPTS" in *..*) echo "no .. in DAYS or INGESTION_RECEIPTS" >&2; exit 2;; esac
ND=$(echo "$DAYS" | tr ',' '\n' | grep -c .); NR=$(echo "$INGESTION_RECEIPTS" | tr ',' '\n' | grep -c .)
[ "$ND" -ge 1 ] && [ "$ND" = "$NR" ] || { echo "DAYS and INGESTION_RECEIPTS must be equal-length comma lists" >&2; exit 2; }
if [ -n "${DAY_EXTERNALS:-}${DAY_EXTERNAL_SHA256S:-}" ]; then
  NX=$(echo "${DAY_EXTERNALS:-}" | tr ',' '\n' | grep -c .); NS=$(echo "${DAY_EXTERNAL_SHA256S:-}" | tr ',' '\n' | grep -c .)
  [ "$NX" = "$ND" ] && [ "$NS" = "$ND" ] || { echo "DAY_EXTERNALS and DAY_EXTERNAL_SHA256S must be comma lists as long as DAYS" >&2; exit 2; }
  case "$DAY_EXTERNALS" in *..*) echo "no .. in DAY_EXTERNALS" >&2; exit 2;; esac
fi
MINE=$(/opt/frankie-box/venv/bin/python -c 'import os; print(" ".join(str(c) for c in sorted(os.sched_getaffinity(0))))') \
  || { echo "could not read this process's CPU affinity" >&2; exit 2; }
NCPU=$(echo "$MINE" | wc -w)
if [ -n "${CPUS:-}" ]; then
  case "$CPUS" in *[!0-9]*|0) echo "CPUS must be a positive integer (the teacher's core budget)" >&2; exit 2;; esac
  [ "$CPUS" -le "$NCPU" ] || { echo "CPUS=$CPUS exceeds the box's $NCPU cores" >&2; exit 2; }
  NCPU=$CPUS
fi
SHARE=$((NCPU / ND)); [ "$SHARE" -ge 2 ] || SHARE=2
[ -z "${CPUS:-}" ] || [ $((SHARE * ND)) -le "$(nproc)" ] || { echo "$ND days need at least $((2 * ND)) cores; CPUS=$NCPU gives $SHARE each" >&2; exit 2; }
echo "### teacher CPU budget: $NCPU of $(nproc) cores, $SHARE per day"
LOGS=/opt/frankie-box/work/experiment-teacher-rows/logs; mkdir -p "$LOGS"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
I=0; PIDS=""
for DAY in $(echo "$DAYS" | tr ',' ' '); do
  I=$((I + 1)); R=$(echo "$INGESTION_RECEIPTS" | cut -d, -f"$I")
  case "$DAY" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) echo "bad day $DAY" >&2; exit 2;; esac
  case "$R" in /opt/frankie-box/work/ingest-*/ingestion-receipt.json) ;; *) echo "bad receipt $R" >&2; exit 2;; esac
  [ -s "$R" ] || { echo "no receipt at $R" >&2; exit 2; }
  FIRST=$(( (I - 1) * SHARE )); LAST=$(( FIRST + SHARE - 1 )); [ "$LAST" -lt "$NCPU" ] || LAST=$((NCPU - 1))
  PIN=$(echo "$MINE" | tr ' ' '\n' | sed -n "$((FIRST + 1)),$((LAST + 1))p" | paste -sd, -)   # positions in the affinity
  SHA=$(sha256sum "$R" | cut -d' ' -f1)
  EXTRA=""
  if [ -n "${DAY_EXTERNALS:-}" ]; then
    X=$(echo "$DAY_EXTERNALS" | cut -d, -f"$I"); XS=$(echo "$DAY_EXTERNAL_SHA256S" | cut -d, -f"$I")
    case "$X" in /opt/frankie-box/*) ;; *) echo "day file $X must be under /opt/frankie-box" >&2; exit 2;; esac
    case "$XS" in [0-9a-f]*) [ "${#XS}" = 64 ] || { echo "bad sha256 $XS" >&2; exit 2; };; *) echo "bad sha256 $XS" >&2; exit 2;; esac
    EXTRA="--day-external $X --day-external-sha256 $XS"
  fi
  LOG="$LOGS/$DAY-$(date +%s).log"
  echo "### $DAY: CPUs $PIN, receipt $R ($SHA), log $LOG ${EXTRA:+(day file given)}"
  # shellcheck disable=SC2086
  taskset -c "$PIN" /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_experiment_teacher.py" \
    --day "$DAY" --ingestion-receipt "$R" --ingestion-receipt-sha256 "$SHA" --workers $((SHARE - 1)) $EXTRA > "$LOG" 2>&1 &
  PIDS="$PIDS $!:$DAY:$LOG"
done
FAILED=0
for P in $PIDS; do
  PID=${P%%:*}; REST=${P#*:}; DAY=${REST%%:*}; LOG=${REST#*:}
  if wait "$PID"; then echo "### $DAY done"; else echo "### $DAY FAILED (listed; the other days go on)"; FAILED=$((FAILED + 1)); fi
  tail -n 40 "$LOG"
done
[ "$FAILED" -eq 0 ] || exit 3
