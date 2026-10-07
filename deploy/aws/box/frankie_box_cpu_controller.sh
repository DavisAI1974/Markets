# The AWS CPU Linux lane controller's LIFETIME on the main box (Step 8A; research/kalshi/frankie_boss/pod_root/controller.py
# --host main). A LISTED, UNUSED FALLBACK (Greg, 2026-10-07: NO days on the small box; every day runs on the main box's two
# held lanes): start and resume refuse unless FALLBACK=worker_box names this route explicitly (with GO); preflight, status,
# stop and clear_stop stay as they are; the main lanes never require this route. The runner-hosted route (frankie_box_run.yml script=deploy/aws/box/frankie_box_pod_root_loop.sh) is a
# bounded GitHub job; this script runs the SAME controller as a run-bound systemd unit on the main box, from the staged
# checkout, the pattern of frankie_box_experiment.sh DETACH=on: the dispatch returns once the unit is up, the runner's
# end cannot stop it, and its state is retained under /opt/frankie-box/work/cpu-controller/<RUN>/.
# Inputs: MARKETS_SHA (the dispatch sets it), CODE_ROOT (the staged clean checkout /opt/frankie-box/code/<dir>/markets at
# MARKETS_SHA), RUN, DAYS (optional comma list YYYYMMDD: the authorized scope the service may claim or resume; default
# every day of the run's saved plan), ACTION:
#   preflight   read-only: the prerequisites beyond source (saved main plan, claim store, staged checkout, the instance
#               profile's credential route to S3 and to the worker over SSM, no live lease) named one by one; exit 2 when
#               one is missing. Nothing is installed, provisioned or created.
#   start       preflight, then the controller as unit frankie-cpu-controller-<RUN>-<epoch> (--action loop --host main
#               --budget-minutes 0: open-ended, until the run's Linux lane has no remaining work or a stop is acknowledged).
#               Refused while a controller of RUN is alive here (lock + process), while an unacknowledged stop request
#               stands, or when a prerequisite is missing. Requires GO=GREG_AWS_GO (Greg's explicit AWS compute go).
#   status      read-only, no AWS call: the controller process (identity, alive, lock, last status, stop request/ack,
#               outcomes) and the worker's LAST-SEEN job, reported distinctly, plus the run's claims. The worker's live
#               state is the runner route's ACTION=status.
#   stop        a cooperative stop: stop-request.json (create-only) with SAVE=on|off (on = the controller relays a save
#               request to the worker's live retained job and waits up to its stop wait for the job to leave its active
#               stages before acknowledging). Prints the request; the acknowledgment is pending until ACTION=status shows
#               stop-ack.json. Never kills the box, the unit or a job; never clears a claim; never writes a completion.
#   resume      JOB=<RUN>-YYYYMMDD-aN: a retained job's same-owner resume requested of the RUNNING service through
#               resume-request.json (create-only; the service, which holds the lane, renews the original job, claim and
#               inputs and resumes it on the worker, or refuses with the reason; its answer is resume-ack-<epoch>.json).
#               Requires GO=GREG_AWS_GO. Without a live service the runner route's ACTION=resume is the way.
#   clear_stop  a stop request that no controller acknowledged (its controller died first) moved aside as
#               stop-request-<epoch>.json so a start is possible again; nothing deleted.
# Retired Pod inputs (PODS, COUNT, CONFIRM, DATA_CENTERS, VOLUME_GB, CONTAINER_GB, WAIT_MINUTES, RUNPOD_API_KEY) are
# refused even when empty. BOXES is fixed to the one Linux lane; SLOTS=1. SSM runs this under sh: POSIX only.
set -eu
export HOME="${HOME:-/root}"
: "${MARKETS_SHA:?full dispatched commit required}"; : "${CODE_ROOT:?staged clean checkout required}"; : "${RUN:?run name required}"
for retired in PODS COUNT CONFIRM DATA_CENTERS VOLUME_GB CONTAINER_GB WAIT_MINUTES RUNPOD_API_KEY; do
  eval "set_=\${$retired+x}"
  [ -z "$set_" ] || { echo "$retired is a retired Pod input; AWS CPU lanes only (refused even when empty)" >&2; exit 2; }
done
ACTION="${ACTION:-status}"
case "$ACTION" in preflight|start|status|stop|resume|clear_stop) ;; *) echo "ACTION must be preflight, start, status, stop, resume or clear_stop" >&2; exit 2;; esac
case "$RUN" in *[!A-Za-z0-9_-]*|"") echo "RUN must be letters, digits, _ or -" >&2; exit 2;; esac
case "$CODE_ROOT" in /opt/frankie-box/code/*/markets) ;; *) echo "CODE_ROOT=/opt/frankie-box/code/<dir>/markets required" >&2; exit 2;; esac
case "$MARKETS_SHA" in *[!0-9a-f]*) echo "MARKETS_SHA must be a full hex commit" >&2; exit 2;; esac
[ "${#MARKETS_SHA}" -eq 40 ] || { echo "MARKETS_SHA must be 40 hex characters" >&2; exit 2; }
[ -d "$CODE_ROOT/.git" ] || [ -f "$CODE_ROOT/.git" ] || { echo "$CODE_ROOT is not a checkout" >&2; exit 2; }
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
[ -z "$(git -C "$CODE_ROOT" status --porcelain --untracked-files=no)" ] || { echo "$CODE_ROOT has tracked changes" >&2; exit 2; }
BOXES="${BOXES:-i-0d17573dbce871520@us-east-1}"; SLOTS="${SLOTS:-1}"
[ "$BOXES" = i-0d17573dbce871520@us-east-1 ] && [ "$SLOTS" = 1 ] || { echo "BOXES=i-0d17573dbce871520@us-east-1 SLOTS=1 is the one Linux lane" >&2; exit 2; }
case "${DATA_WORKERS:-15}${POLL_SECONDS:-60}${STOP_WAIT_MINUTES:-30}" in *[!0-9]*) echo "DATA_WORKERS, POLL_SECONDS and STOP_WAIT_MINUTES must be whole numbers" >&2; exit 2;; esac
case "${DAYS:-}" in *[!0-9,]*) echo "DAYS must be a comma list of YYYYMMDD" >&2; exit 2;; esac
CONTROLLER="$CODE_ROOT/research/kalshi/frankie_boss/pod_root/controller.py"
PY=/opt/frankie-box/venv/bin/python
STATE="/opt/frankie-box/work/cpu-controller/$RUN"
LOG="/opt/frankie-box/logs/cpu-controller-$RUN.log"
[ -f "$CONTROLLER" ] || { echo "$CODE_ROOT holds no pod_root/controller.py: stage a commit that has it" >&2; exit 2; }
[ -f "$CODE_ROOT/deploy/aws/ssm_run_sh.py" ] && [ -f "$CODE_ROOT/deploy/aws/box/frankie_box_pod_root.sh" ] || { echo "$CODE_ROOT lacks ssm_run_sh.py or frankie_box_pod_root.sh" >&2; exit 2; }
[ -x "$PY" ] || { echo "no $PY: the box venv is a prerequisite (frankie_box_worker_setup.sh made it); not installed here" >&2; exit 2; }
"$PY" -c 'import boto3, botocore' 2>/dev/null || { echo "boto3 is not importable from $PY: the venv pins are a prerequisite; not installed here" >&2; exit 2; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
set -- --run "$RUN" --code-root "$CODE_ROOT" --host main --state-dir "$STATE" --boxes "$BOXES" --slots "$SLOTS" \
  --data-workers "${DATA_WORKERS:-15}" --poll-seconds "${POLL_SECONDS:-60}" --stop-wait-minutes "${STOP_WAIT_MINUTES:-30}" \
  --days "${DAYS:-}"
# A live controller holds $STATE/controller.lock for its lifetime (fcntl); its pid is in controller.json. Liveness is the
# lock, never a command-line pattern.
alive_pids() {
  [ -e "$STATE/controller.lock" ] || return 0
  "$PY" -B -c 'import sys; sys.path.insert(0, sys.argv[1]); import controller; p = controller.alive_pid(sys.argv[2]); print(p if p else "", end="")' \
    "$CODE_ROOT/research/kalshi/frankie_boss/pod_root" "$STATE" 2>/dev/null
}
case "$ACTION" in
  preflight)
    exec "$PY" -B "$CONTROLLER" --action preflight --commit "$MARKETS_SHA" "$@" ;;
  status)
    echo "### controller processes of $RUN on this host: $(alive_pids | tr '\n' ' ')"
    echo "### unit(s): $(systemctl list-units --no-legend --plain "frankie-cpu-controller-$RUN-*" 2>/dev/null | tr '\n' ';')"
    [ ! -f "$LOG" ] || { echo "### log tail $LOG"; tail -n 20 "$LOG"; }
    exec "$PY" -B "$CONTROLLER" --action retained "$@" ;;
  stop)
    case "${SAVE:-on}" in on|off) ;; *) echo "SAVE must be on or off" >&2; exit 2;; esac
    PIDS="$(alive_pids | tr '\n' ' ')"
    [ -n "$PIDS" ] || { echo "no controller of $RUN is alive on this host; nothing to stop (a worker job, if any, is untouched; the runner route ACTION=stop JOB=... requests its save directly)" >&2; exit 3; }
    mkdir -p "$STATE"
    if [ -e "$STATE/stop-request.json" ]; then
      echo "a stop request already stands: $STATE/stop-request.json; acknowledgment: $([ -e "$STATE/stop-ack.json" ] && echo written || echo pending)" >&2
      cat "$STATE/stop-request.json" >&2; exit 3
    fi
    SAVE_JSON=false; [ "${SAVE:-on}" = off ] || SAVE_JSON=true
    TMP="$STATE/.stop-request.$$"
    printf '{"schema":"FRANKIE_CPU_CONTROLLER_V1_STOP_REQUEST","run":"%s","requested_utc":"%s","requested_epoch":%s,"save":%s,"by":"frankie_box_cpu_controller.sh","controller_pids":"%s"}\n' \
      "$RUN" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(date +%s)" "$SAVE_JSON" "$PIDS" > "$TMP"
    if ln "$TMP" "$STATE/stop-request.json" 2>/dev/null; then rm -f "$TMP"; else rm -f "$TMP"; echo "a stop request was written meanwhile; not replaced" >&2; exit 3; fi
    echo "stop requested (save=${SAVE:-on}); the controller (pids $PIDS) acknowledges at its next poll: ACTION=status shows stop-ack.json"
    cat "$STATE/stop-request.json"
    exit 0 ;;
  resume)
    [ "${FALLBACK:-}" = worker_box ] || { echo "the worker-box lane is a listed, unused fallback (every day runs on the main box's two lanes): FALLBACK=worker_box (an explicit decision) required; nothing requested" >&2; exit 2; }
    [ "${GO:-}" = GREG_AWS_GO ] || { echo "resume starts compute on the worker: GO=GREG_AWS_GO (Greg's explicit go) required; nothing requested" >&2; exit 2; }
    case "${JOB:-}" in "$RUN"-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-a[0-9]*) ;; *) echo "JOB must name the original $RUN-YYYYMMDD-aN attempt" >&2; exit 2;; esac
    case "$JOB" in *[!A-Za-z0-9_-]*) echo "JOB carries a character outside [A-Za-z0-9_-]" >&2; exit 2;; esac
    PIDS="$(alive_pids | tr '\n' ' ')"
    [ -n "$PIDS" ] || { echo "no controller of $RUN is alive on this host: the runner route (frankie_box_pod_root_loop.sh ACTION=resume JOB=$JOB) resumes without a service" >&2; exit 3; }
    [ ! -e "$STATE/stop-request.json" ] || { echo "a stop request stands; no resume while stopping" >&2; exit 3; }
    [ ! -e "$STATE/resume-request.json" ] || { echo "a resume request already stands (unanswered): $STATE/resume-request.json" >&2; cat "$STATE/resume-request.json" >&2; exit 3; }
    TMP="$STATE/.resume-request.$$"
    printf '{"schema":"FRANKIE_CPU_CONTROLLER_V1_RESUME_REQUEST","run":"%s","job_id":"%s","requested_utc":"%s","requested_epoch":%s,"by":"frankie_box_cpu_controller.sh","controller_pids":"%s"}\n' \
      "$RUN" "$JOB" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(date +%s)" "$PIDS" > "$TMP"
    if ln "$TMP" "$STATE/resume-request.json" 2>/dev/null; then rm -f "$TMP"; else rm -f "$TMP"; echo "a resume request was written meanwhile; not replaced" >&2; exit 3; fi
    echo "resume of $JOB requested of the controller (pids $PIDS); its answer lands as $STATE/resume-ack-<epoch>.json (ACTION=status)"
    cat "$STATE/resume-request.json"
    exit 0 ;;
  clear_stop)
    [ -e "$STATE/stop-request.json" ] || { echo "no stop request stands for $RUN"; exit 0; }
    [ ! -e "$STATE/stop-ack.json" ] || { echo "the stop request of $RUN was acknowledged; a start archives both itself" >&2; exit 3; }
    PIDS="$(alive_pids | tr '\n' ' ')"
    [ -z "$PIDS" ] || { echo "a controller of $RUN is alive (pids $PIDS): its stop request is not cleared under it" >&2; exit 3; }
    STAMP="$(date +%s)"; mv "$STATE/stop-request.json" "$STATE/stop-request-$STAMP.json"
    echo "moved aside: $STATE/stop-request-$STAMP.json (nothing deleted)" ;;
  start)
    [ "${FALLBACK:-}" = worker_box ] || { echo "the worker-box lane is a listed, unused fallback (every day runs on the main box's two lanes): FALLBACK=worker_box (an explicit decision) required; nothing started" >&2; exit 2; }
    [ "${GO:-}" = GREG_AWS_GO ] || { echo "start is AWS compute coordination: GO=GREG_AWS_GO (Greg's explicit go) required; nothing started" >&2; exit 2; }
    command -v systemd-run >/dev/null || { echo "systemd-run is a prerequisite on this host; nothing started" >&2; exit 2; }
    PIDS="$(alive_pids | tr '\n' ' ')"
    [ -z "$PIDS" ] || { echo "a controller of $RUN is alive on this host (pids $PIDS); not started twice" >&2; exit 3; }
    mkdir -p "$STATE" /opt/frankie-box/logs
    STAMP="$(date +%s)"
    if [ -e "$STATE/stop-request.json" ]; then
      if [ -e "$STATE/stop-ack.json" ]; then
        mv "$STATE/stop-request.json" "$STATE/stop-request-$STAMP.json"; mv "$STATE/stop-ack.json" "$STATE/stop-ack-$STAMP.json"
        echo "the acknowledged stop of a previous start archived as stop-request-$STAMP.json / stop-ack-$STAMP.json"
      else
        echo "an unacknowledged stop request stands ($STATE/stop-request.json): its controller died before acknowledging; read it, then ACTION=clear_stop; nothing started" >&2; exit 3
      fi
    elif [ -e "$STATE/stop-ack.json" ]; then
      mv "$STATE/stop-ack.json" "$STATE/stop-ack-$STAMP.json"
      echo "an acknowledgment without its request (orphan) archived as stop-ack-$STAMP.json"
    fi
    if [ -e "$STATE/resume-request.json" ] && [ ! -e "$STATE/resume-pending.json" ]; then
      echo "a resume request stands that no controller took ($STATE/resume-request.json): read it; move it aside by hand (nothing here deletes it); nothing started" >&2; exit 3
    fi
    [ ! -e "$STATE/resume-pending.json" ] || echo "a resume is pending from a previous controller ($STATE/resume-pending.json): the new controller reconciles it through the worker status; it is never re-sent"

    "$PY" -B "$CONTROLLER" --action preflight --commit "$MARKETS_SHA" "$@" || { echo "preflight refused activation (above); nothing started" >&2; exit 2; }
    UNIT="frankie-cpu-controller-$RUN-$STAMP"
    MARK="$STATE/.start-$STAMP"; : > "$MARK"
    # S2 (stacks pass 2026-10-07): KillMode=mixed: a stop signals the controller (main process) only; the stage children
    # it runs and their pool workers are not SIGTERMed with it (the default control-group mode made a parent redo their
    # work with one fewer before its save point); the remainder is SIGKILLed at TimeoutStopSec
    systemd-run --unit "$UNIT" --collect -p StandardOutput=append:"$LOG" -p StandardError=append:"$LOG" -p KillMode=mixed \
      -E HOME="$HOME" -E PYTHONDONTWRITEBYTECODE=1 -E PYTHONNOUSERSITE=1 -E PYTHONPATH="$CODE_ROOT" -E CPU_CONTROLLER_UNIT="$UNIT" \
      "$PY" -B "$CONTROLLER" --action loop --commit "$MARKETS_SHA" --budget-minutes 0 --fallback-route worker_box "$@"
    echo "controller of $RUN started as unit $UNIT, log $LOG, state $STATE"
    sleep 10
    if ! systemctl is-active "$UNIT"; then
      ENDED="$(find "$STATE" -maxdepth 1 -name 'outcome-*.json' -newer "$MARK" | head -n 1)"
      rm -f "$MARK"
      if [ -n "$ENDED" ]; then
        echo "the controller ended on its own within 10 s; its outcome $ENDED:"; cat "$ENDED"; tail -n 20 "$LOG"
        # no_remaining_work is a clean end (nothing for the Linux lane); anything else means the start did not take
        OUTCOME="$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1])).get("outcome") or "")' "$ENDED" 2>/dev/null)"
        [ "$OUTCOME" = no_remaining_work ] && exit 0
        echo "the start did not take (outcome $OUTCOME); read the outcome and the log above" >&2; exit 3
      fi
      echo "the unit is not active 10 s after start and wrote no outcome; log tail:"; tail -n 40 "$LOG"; exit 3
    fi
    rm -f "$MARK"
    tail -n 20 "$LOG"
    [ ! -f "$STATE/controller.json" ] || cat "$STATE/controller.json"
    exit 0 ;;
esac
