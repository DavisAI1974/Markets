# The experiment orchestrator (frankie_box_experiment.py; SPEC-experiment-orchestrator.md "How the orchestrator runs"):
# one run over a list of days of ONE class, calling the committed steps in order (fetch, ingest, external, root, teacher,
# classroom, jev, data, search, lessons, exchange, voice (not wired: records waiting), school, reports), a receipt per day
# and step under /opt/frankie-box/work/experiment/<RUN>/, resume on restart, a stop
# and save at the disk floor. No data dropped: a day's gap waits or is skipped over on that day's steps (listed), the
# rest runs. No model call, no Granite, no Pod.
# Inputs: CODE_ROOT (staged checkout), ACTION (plan | start | status; default plan, read-only), RUN (the run name),
# DAYS (comma list YYYYMMDD) and/or PLAN (a plan JSON, repo-relative or under /opt/frankie-box), DAY_CLASS (monday |
# midweek | thursday | friday), CLASSROOM_ARM (comma list), FROZEN_SURVIVORS (confirmation days only), HISTORICAL_CLAIMS
# (repo-relative committed file), STAGES (comma list),
# LAGS, TRANSFORMS, INGEST_WORKERS (31, a ceiling: each ingest day process books 8 CPUs and runs the most that fit), DATA_WORKERS /
# SEARCH_WORKERS / TEACHER_CPUS (not used: every day-run step books exactly 16 CPUs in the box's ledger, frankie_box_cores.py,
# and runs 15 workers; a step that cannot book 16 waits), PARALLEL_DAYS (2: the two main-box lanes), DISK_FLOOR_GB (100),
# EXTERNAL_HISTORY_RUN (the day_history run id the day files are built from), EXTERNAL_HISTORY_EIA930_RUN (optional
# second run id for the eia930 family), EXTERNAL_HISTORY_FAMILY_RUNS (optional family=<run id>,...), EXTERNAL_WAIT (on|off), BRAIN,
# PREVIOUS_CLASSROOM (the run's first arm day), MAP_URL (the dispatch's presigned map: the partitions for fetch, the
# day history and curve prefixes and the day-file slots for external, Jev's material slots for jev; ACTION=plan prints
# the whole presign string), FRANKIE_QUEUE (on|off, default on: classroom-arm days enter Frankie's class line, arrival
# FIFO, one class at a time), ROOT_QUEUE (on|off, default on: ROOT-ready days enter the ROOT line, arrival FIFO to the next
# free day-run slot), QUEUE_WORKER_SECONDS (43200: a kicked queue worker's bound and the wait on this run's ROOT-line
# days), QUEUE_POLL_SECONDS (60). A probe: frankie_box_progress.sh DIRECTORY=/opt/frankie-box/work/experiment/<RUN>; the
# queue: frankie_box_frankie_queue.sh ACTION=show.
set -eu
export HOME="${HOME:-/root}"   # SSM runs without HOME; DuckDB refuses to load extensions without a home directory (2026-09-29)
: "${MARKETS_SHA:?full dispatched commit required}"; : "${CODE_ROOT:?staged clean checkout required}"; : "${RUN:?run name required}"
ACTION="${ACTION:-plan}"
case "$ACTION" in plan|start|status|successor-request|successor-decision|successor-retry|successor-save|successor-resume|voice-dispatched|voice-returned) ;; *) echo "unknown experiment ACTION" >&2; exit 2;; esac
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
set -- --action "$ACTION" --run "$RUN" --commit "$MARKETS_SHA" --code-root "$CODE_ROOT"
case "$ACTION" in successor-*)
  : "${SUCCESSOR_DAY:?owning day required}"
  set -- "$@" --successor-day "$SUCCESSOR_DAY"
  if [ -n "${SUCCESSOR_FILE:-}" ]; then
    case "$SUCCESSOR_FILE" in /opt/frankie-box/work/experiment/*) ;; *) echo "SUCCESSOR_FILE must be owner-local" >&2; exit 2;; esac
    case "$SUCCESSOR_FILE" in *..*) exit 2;; esac
    set -- "$@" --successor-file "$SUCCESSOR_FILE"
  fi
  [ -z "${SUCCESSOR_ID:-}" ] || set -- "$@" --successor-id "$SUCCESSOR_ID"
;; esac
# the remote (GitHub) meeting route's owner records (Step 6 caller): the exact dispatched run, then its return; nothing
# here dispatches a workflow or calls GitHub
case "$ACTION" in voice-*)
  : "${VOICE_DAY:?classroom-arm day required}"
  case "$VOICE_DAY" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) echo "VOICE_DAY must be YYYYMMDD" >&2; exit 2;; esac
  set -- "$@" --voice-day "$VOICE_DAY" --voice-by "${VOICE_BY:-operator}"
  if [ "$ACTION" = voice-dispatched ]; then
    case "${VOICE_GITHUB_RUN:-}" in ""|*[!0-9]*) echo "VOICE_GITHUB_RUN must be the numeric GitHub run id" >&2; exit 2;; esac
    case "${VOICE_GITHUB_ATTEMPT:-1}" in *[!0-9]*) echo "VOICE_GITHUB_ATTEMPT must be numeric" >&2; exit 2;; esac
    set -- "$@" --voice-github-run "$VOICE_GITHUB_RUN" --voice-github-attempt "${VOICE_GITHUB_ATTEMPT:-1}"
  else
    case "${VOICE_ARCHIVE:-}" in /opt/frankie-box/work/experiment/*) ;; *) echo "VOICE_ARCHIVE must be the downloaded runner-state.zip under /opt/frankie-box/work/experiment" >&2; exit 2;; esac
    case "$VOICE_ARCHIVE" in *..*) exit 2;; esac
    case "${VOICE_ARCHIVE_SHA256:-}" in [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;; *) echo "VOICE_ARCHIVE_SHA256 required (hex)" >&2; exit 2;; esac
    case "${VOICE_CONCLUSION:-}" in success|failure|cancelled|timed_out|lost) ;; *) echo "VOICE_CONCLUSION must be success|failure|cancelled|timed_out|lost" >&2; exit 2;; esac
    set -- "$@" --voice-archive "$VOICE_ARCHIVE" --voice-archive-sha256 "$VOICE_ARCHIVE_SHA256" --voice-conclusion "$VOICE_CONCLUSION"
  fi
;; esac
[ -z "${PLAN:-}" ] || set -- "$@" --plan "$PLAN"
[ -z "${DAYS:-}" ] || set -- "$@" --days "$DAYS"
[ -z "${DAY_CLASS:-}" ] || set -- "$@" --day-class "$DAY_CLASS"
[ -z "${CLASSROOM_ARM:-}" ] || set -- "$@" --classroom-arm "$CLASSROOM_ARM"
[ -z "${CLASSROOM_ARM_CYCLE:-}" ] || set -- "$@" --classroom-arm-cycle "$CLASSROOM_ARM_CYCLE"
[ -z "${FROZEN_SURVIVORS:-}" ] || set -- "$@" --frozen-survivors "$FROZEN_SURVIVORS"
[ -z "${HISTORICAL_CLAIMS:-}" ] || set -- "$@" --historical-claims "$HISTORICAL_CLAIMS"
[ -z "${STAGES:-}" ] || set -- "$@" --stages "$STAGES"
[ -z "${TRANSFORMS:-}" ] || set -- "$@" --transforms "$TRANSFORMS"
case "${EXTERNAL_HISTORY_RUN:-}" in ""|*[!0-9]*) [ -z "${EXTERNAL_HISTORY_RUN:-}" ] || { echo "EXTERNAL_HISTORY_RUN must be the numeric run id" >&2; exit 2; };; esac
[ -z "${EXTERNAL_HISTORY_RUN:-}" ] || set -- "$@" --external-history-run "$EXTERNAL_HISTORY_RUN"
case "${EXTERNAL_HISTORY_EIA930_RUN:-}" in *[!0-9]*) echo "EXTERNAL_HISTORY_EIA930_RUN must be the numeric run id" >&2; exit 2;; esac
[ -z "${EXTERNAL_HISTORY_EIA930_RUN:-}" ] || set -- "$@" --external-eia930-history-run "$EXTERNAL_HISTORY_EIA930_RUN"
case "${EXTERNAL_HISTORY_FAMILY_RUNS:-}" in *[!a-z0-9_=,]*) echo "EXTERNAL_HISTORY_FAMILY_RUNS must be family=<run id>,..." >&2; exit 2;; esac
[ -z "${EXTERNAL_HISTORY_FAMILY_RUNS:-}" ] || set -- "$@" --external-family-history-runs "$EXTERNAL_HISTORY_FAMILY_RUNS"
case "${EXTERNAL_WAIT:-on}" in on|off) ;; *) echo "EXTERNAL_WAIT must be on or off" >&2; exit 2;; esac
set -- "$@" --external-wait "${EXTERNAL_WAIT:-on}" --brain "${BRAIN:-/opt/frankie-box/brain}"
# Jev's brain, saved in the plan when given at the first start (Step 7). JEV_RUNTIME is REFUSED (Greg, 2026-10-07): Jev
# uses the same weights, code and setup as the Granite meeting, the ONE pinned runtime installed on the box by
# frankie_box_granite_meeting_setup.sh (Run.jev binds to it; no second install, no second pin set)
[ -z "${JEV_RUNTIME:-}" ] || { echo "JEV_RUNTIME is retired: Jev binds to the one pinned runtime shared with the Granite meeting (GRANITE_MEETING_RUNTIME_V1, /opt/frankie-box/granite); no separate Jev runtime" >&2; exit 2; }
[ -z "${JEV_BRAIN:-}" ] || set -- "$@" --jev-brain "$JEV_BRAIN"
# the per-piece status reports (Greg, 2026-10-07: the ONE-day run only), saved with the plan at its first start: auto
# (default: one_day when the plan holds exactly one day, else off), one_day or off; an existing run keeps its saved value
case "${INSPECTION:-auto}" in
  auto|one_day|off) set -- "$@" --inspection "${INSPECTION:-auto}" ;;
  *) echo "INSPECTION must be auto, one_day or off" >&2; exit 2;;
esac
# the bounded meeting's host route (Step 6 caller), saved with the plan at its first start: local (default) or github
case "${VOICE_ROUTE:-local}" in
  local) ;;
  github) set -- "$@" --voice-route github ;;
  *) echo "VOICE_ROUTE must be local or github" >&2; exit 2;;
esac
# the synchronized shared market input of a NEW run (Greg, 2026-10-07), saved with the plan at its first start; unset =
# the orchestrator's default: a NEW run selects it (native pass on), an existing run keeps its saved plan's value
case "${SHARED_MARKET_POLICY:-}" in
  '') ;;
  FRANKIE_SHARED_MARKET_TIMELINE_V1) set -- "$@" --shared-market-policy "$SHARED_MARKET_POLICY" ;;
  *) echo "unknown SHARED_MARKET_POLICY" >&2; exit 2;;
esac
case "${BRAIN:-/opt/frankie-box/brain}${PREVIOUS_CLASSROOM:-}${JEV_BRAIN:-}" in *..*) echo "no .. in BRAIN, PREVIOUS_CLASSROOM or JEV_BRAIN" >&2; exit 2;; esac
case "${JEV_BRAIN:-}" in ""|/opt/frankie-box/*) ;; *) echo "JEV_BRAIN must be an absolute path under /opt/frankie-box" >&2; exit 2;; esac
case "${BRAIN:-/opt/frankie-box/brain}" in /opt/frankie-box/*) ;; *) echo "BRAIN must be under /opt/frankie-box" >&2; exit 2;; esac
case "${PREVIOUS_CLASSROOM:-}" in ""|/opt/frankie-box/work/experiment-roots/*/work/classroom) ;; *) echo "PREVIOUS_CLASSROOM must be an experiment root's work/classroom" >&2; exit 2;; esac
[ -z "${PREVIOUS_CLASSROOM:-}" ] || set -- "$@" --previous-classroom "$PREVIOUS_CLASSROOM"
case "${FRANKIE_QUEUE:-on}${ROOT_QUEUE:-on}" in onon|onoff|offon|offoff) ;; *) echo "FRANKIE_QUEUE and ROOT_QUEUE must be on or off" >&2; exit 2;; esac
case "${QUEUE_WORKER_SECONDS:-43200}${QUEUE_POLL_SECONDS:-60}" in *[!0-9]*) echo "QUEUE_WORKER_SECONDS and QUEUE_POLL_SECONDS must be whole seconds" >&2; exit 2;; esac
set -- "$@" --frankie-queue "${FRANKIE_QUEUE:-on}" --root-queue "${ROOT_QUEUE:-on}" \
  --queue-worker-seconds "${QUEUE_WORKER_SECONDS:-43200}" --queue-poll-seconds "${QUEUE_POLL_SECONDS:-60}"
set -- "$@" --lags "${LAGS:-20}" --ingest-workers "${INGEST_WORKERS:-31}" --data-workers "${DATA_WORKERS:-1}" \
  --search-workers "${SEARCH_WORKERS:-8}" --teacher-cpus "${TEACHER_CPUS:-0}" --parallel-days "${PARALLEL_DAYS:-2}" --disk-floor-gb "${DISK_FLOOR_GB:-100}"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT" MAP_URL="${MAP_URL:-}"
# DETACH=on (ACTION=start only; 2026-09-30, "never leave a job on a GitHub runner that can outlast its 6 h limit"): the
# start runs as its own systemd unit, not under the SSM command, so the runner's 6 h end (and its cancel step) cannot stop
# it; the dispatch returns once the unit is up. Refused while any start of the same RUN is alive (never two orchestrators
# on one run). Log: /opt/frankie-box/logs/experiment-<RUN>.log; probe as before (frankie_box_progress.sh).
case "${DETACH:-off}" in on|off) ;; *) echo "DETACH must be on or off" >&2; exit 2;; esac
if [ "${DETACH:-off}" = on ]; then
  [ "$ACTION" = start ] || { echo "DETACH=on is for ACTION=start only" >&2; exit 2; }
  case "$RUN" in *[!A-Za-z0-9_-]*) echo "RUN must be letters, digits, _ or -" >&2; exit 2;; esac
  command -v systemd-run >/dev/null || { echo "DETACH=on needs systemd-run on the box" >&2; exit 2; }
  if pgrep -f -- "frankie_box_experiment.py --action start --run $RUN " >/dev/null; then
    echo "an orchestrator start of $RUN is alive (pids: $(pgrep -f -- "frankie_box_experiment.py --action start --run $RUN " | tr '\n' ' ')); not started twice" >&2
    exit 3
  fi
  mkdir -p /opt/frankie-box/logs
  LOG="/opt/frankie-box/logs/experiment-$RUN.log"; UNIT="frankie-experiment-$RUN-$(date +%s)"
  set -- -E HOME="$HOME" -E PYTHONDONTWRITEBYTECODE=1 -E PYTHONNOUSERSITE=1 -E PYTHONPATH="$CODE_ROOT" -E MAP_URL="$MAP_URL" \
    /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_experiment.py" "$@"
  systemd-run --unit "$UNIT" --collect -p StandardOutput=append:"$LOG" -p StandardError=append:"$LOG" "$@"
  echo "orchestrator $RUN started detached: unit $UNIT, log $LOG"
  sleep 10
  systemctl is-active "$UNIT" || { echo "the unit is not active 10 s after start; log tail:"; tail -n 40 "$LOG"; exit 3; }
  tail -n 20 "$LOG"
  exit 0
fi
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_experiment.py" "$@"
