# Frankie's FIFO queue (frankie_box_frankie_queue.py; Greg, 2026-09-29: "I don't want any days dropped and moved forward
# because he was busy"; "order by first in the pod first out the pod or box"; "And the root calcs too"; "Class days are
# sequential"). Two lines under /opt/frankie-box/work/frankie-queue/, each arrival-order FIFO (enqueued_at then a
# monotonic seq): the ROOT line (a day enters when its sealed ingest and day file are there; days leave in arrival order
# to the next free day-run slot, box or Pod) and the CLASS line (an arm day enters when its ROOT, teacher rows and day file
# are there; ONE class at a time, school day = position in the line = report number N, each class carrying the last class
# to finish). Nothing dropped, skipped or reordered. No model call, no Pod call, no Granite, no Databento.
# Inputs: CODE_ROOT (staged checkout; default the newest staged one), ACTION:
#   show                         read-only: both lines, every entry with its state and reason, the workers [EVENTS=50|all]
#   enqueue LINE RUN DAY         the orchestrator's own readiness checks on the run's saved plan, then the entry [KICK=on]
#   worker  LINE SCOPE           the line's one worker in the foreground, until its scope is done [MAX_SECONDS opt-in]; a
#                                second worker exits at once; exit 0 idle, 3 stopped at a failed entry, 5 saved at the bound
#                                or waiting (an owner's resume, or an out-of-scope predecessor at the front)
#   kick    LINE SCOPE           starts the line's worker detached (systemd-run) unless one runs [MAX_SECONDS opt-in, 0=none]
# SCOPE=RUN:YYYYMMDD,... is the authorization a worker/kick/handover carries: it admits, reconciles and receipts ONLY
# those run/days; everything else in the line is left exactly as it is (FIFO still makes an eligible day wait behind an
# unstarted predecessor; the predecessor is never started by that worker).
#   handover LINE=root           the running worker stops taking work and ends after its running days; a new worker at
#                                this commit (every day runs its whole day in its slot) waits on the lock and takes over
#   save    RUN DAY              the day-bound save of a running owned day: its marker written; the owner stops at its
#                                next boundary (a class in progress acknowledges first); acknowledgment pending = status
#           [RELEASE_BOOKING=on] the fleet classroom gate's fleet_waiting save ONLY: the booking is RELEASED at that
#                                boundary (recorded with its CPU set) instead of retained; ACTION=resume re-books it
#   status  RUN DAY              read-only: the owner binding, marker, class acknowledgment, ledger booking (live /
#                                retained / released), both line entries and the worker, distinctly
#   resume  RUN DAY [REBOOK=on]  a saved/unknown owned day back in line with the SAME owner (attempt, CPUs, marker
#                                archived); refused when its retained booking is gone unless REBOOK=on (the same attempt
#                                on any free 16 CPUs, an explicit decision); then kick LINE=root (SCOPE=RUN:...)
#   retire  RUN REASON           a dead run's line entries leave both lines (kept whole under each line's `retired` list
#                                with who/when/why; nothing deleted), so its duplicate-data claim no longer blocks a new
#                                run of the same day; refused while one of its entries runs under a live worker
# Every day follows the worker's current source on its next admission (recorded on the entry as source_rebinds; its
# stages' own data checks still decide). 2026-10-09: the code version is recorded, never compared.
# LINE is root or class. MARKETS_SHA (the dispatched commit) is recorded; the checkout's own HEAD is what runs.
set -eu
export HOME="${HOME:-/root}"
# 2026-10-09 (Greg: the code version is recorded, never compared): CODE_ROOT defaults to the NEWEST staged checkout on
# the box (frankie_box_cpu_watch.newest_staged_checkout's rule: staging-receipt.json status 'staged' for the directory's
# own commit, newest by the receipt's mtime) and MARKETS_SHA to that checkout's HEAD
if [ -z "${CODE_ROOT:-}" ]; then
  CODE_ROOT=$(/opt/frankie-box/venv/bin/python -I -S -B -c '
import json, os, re
best, parent = None, "/opt/frankie-box/code"
for name in (os.listdir(parent) if os.path.isdir(parent) else []):
    d = os.path.join(parent, name)
    m = re.fullmatch(r"([0-9a-f]{40})-[A-Za-z0-9_-]{1,96}", name)
    r, c = os.path.join(d, "staging-receipt.json"), os.path.join(d, "markets")
    if not m or os.path.islink(d) or not os.path.isfile(r):
        continue
    try:
        v = json.load(open(r))
    except ValueError:
        continue
    if v.get("status") == "staged" and v.get("commit") == m.group(1) and v.get("code_root") == c and os.path.isdir(c):
        t = os.stat(r).st_mtime
        if best is None or t > best[0]:
            best = (t, c)
print(best[1] if best else "")') || CODE_ROOT=''
  [ -n "$CODE_ROOT" ] || { echo "no CODE_ROOT given and no staged checkout under /opt/frankie-box/code" >&2; exit 2; }
  echo "### CODE_ROOT not given: the newest staged checkout $CODE_ROOT" >&2
fi
MARKETS_SHA="${MARKETS_SHA:-$(git -C "$CODE_ROOT" rev-parse HEAD 2>/dev/null || true)}"
ACTION="${ACTION:-show}"
case "$ACTION" in show|enqueue|worker|kick|handover|save|status|resume|retire) ;; *) echo "ACTION must be show, enqueue, worker, kick, handover, save, status, resume or retire" >&2; exit 2;; esac
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
case "$CODE_ROOT" in *..*) echo "no .. in CODE_ROOT" >&2; exit 2;; esac
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
# FA-6 (2026-10-07): the operator's FRANKIE_* run settings (e.g. FRANKIE_ROOT_NATIVE_OVERLAP=off as a dispatch variable,
# a plain shell variable under ssm_run_sh.py) are exported, so a kick/handover passes them to the worker it starts
# (frankie_box_frankie_queue._run_settings_env, recorded in the kick receipt). Never: per-process lane/booking/claim
# identity, anything named like a credential, a multi-line value.
NL='
'
for NAME in $(set | sed -n 's/^\(FRANKIE_[A-Za-z0-9_]*\)=.*/\1/p' | sort -u); do
  case "$NAME" in FRANKIE_LANE_*|FRANKIE_BOOKED_CPUS|FRANKIE_CPU_BOOKING|FRANKIE_STEP_CLAIM|FRANKIE_STAGE_PROGRESS) continue;; esac
  case "$NAME" in *TOKEN*|*SECRET*|*PASSWORD*|*CREDENTIAL*|*_KEY|*_KEY_*) continue;; esac
  eval "[ -n \"\${$NAME+x}\" ]" || continue
  eval "VALUE=\${$NAME}"
  case "$VALUE" in *"$NL"*) continue;; esac
  export "$NAME"
done
PY=/opt/frankie-box/venv/bin/python
SCRIPT="$CODE_ROOT/deploy/aws/box/frankie_box_frankie_queue.py"
if [ "$ACTION" = show ]; then
  case "${EVENTS:-50}" in all) ;; ""|*[!0-9]*) echo "EVENTS must be a number or all" >&2; exit 2;; esac
  exec "$PY" -B "$SCRIPT" --action show --events "${EVENTS:-50}"
fi
if [ "$ACTION" = retire ]; then
  : "${RUN:?the dead run name required}"; : "${REASON:?REASON (recorded on every retired entry) required}"
  case "$RUN" in ""|*[!A-Za-z0-9_-]*) echo "RUN: letters, digits, _ and - only" >&2; exit 2;; esac
  HEAD_SHA=$(git -C "$CODE_ROOT" rev-parse HEAD 2>/dev/null) || HEAD_SHA="${MARKETS_SHA:-}"  # 2026-10-09: recorded, never compared
  [ "$HEAD_SHA" = "${MARKETS_SHA:-}" ] || { echo "code version: MARKETS_SHA ${MARKETS_SHA:-unset}, checkout $CODE_ROOT at $HEAD_SHA; this step runs on (and records) $HEAD_SHA" >&2; MARKETS_SHA=$HEAD_SHA; }
  exec "$PY" -B "$SCRIPT" --action retire --run "$RUN" --reason "$REASON"
fi
case "$ACTION" in save|status|resume)
  : "${RUN:?the orchestrator run name required}"; : "${DAY:?YYYYMMDD required}"
  case "$RUN" in ""|*[!A-Za-z0-9_-]*) echo "RUN: letters, digits, _ and - only" >&2; exit 2;; esac
  case "$DAY" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) echo "DAY must be YYYYMMDD" >&2; exit 2;; esac
  if [ "$ACTION" != status ]; then
    HEAD_SHA=$(git -C "$CODE_ROOT" rev-parse HEAD 2>/dev/null) || HEAD_SHA="${MARKETS_SHA:-}"  # 2026-10-09: recorded, never compared
    [ "$HEAD_SHA" = "${MARKETS_SHA:-}" ] || { echo "code version: MARKETS_SHA ${MARKETS_SHA:-unset}, checkout $CODE_ROOT at $HEAD_SHA; this step runs on (and records) $HEAD_SHA" >&2; MARKETS_SHA=$HEAD_SHA; }
  fi
  case "${REBOOK:-off}" in on|off) ;; *) echo "REBOOK must be on or off" >&2; exit 2;; esac
  # session 8 (B4): RELEASE_BOOKING=on on ACTION=save releases the day's CPU booking at the save boundary (the fleet
  # classroom gate's fleet_waiting save ONLY; RELEASE_REASON recorded); off (default) retains it exactly as before
  case "${RELEASE_BOOKING:-off}" in on|off) ;; *) echo "RELEASE_BOOKING must be on or off" >&2; exit 2;; esac
  set -- --action "$ACTION" --run "$RUN" --day "$DAY" --rebook "${REBOOK:-off}" --release-booking "${RELEASE_BOOKING:-off}"
  [ -z "${RELEASE_REASON:-}" ] || set -- "$@" --release-reason "$RELEASE_REASON"
  exec "$PY" -B "$SCRIPT" "$@" ;;
esac
HEAD_SHA=$(git -C "$CODE_ROOT" rev-parse HEAD 2>/dev/null) || HEAD_SHA="${MARKETS_SHA:-}"  # 2026-10-09: recorded, never compared
[ "$HEAD_SHA" = "${MARKETS_SHA:-}" ] || { echo "code version: MARKETS_SHA ${MARKETS_SHA:-unset}, checkout $CODE_ROOT at $HEAD_SHA; this step runs on (and records) $HEAD_SHA" >&2; MARKETS_SHA=$HEAD_SHA; }
case "${LINE:-}" in root|class) ;; *) echo "LINE must be root or class" >&2; exit 2;; esac
# 2026-10-09: no POLL_SECONDS: every queue wait is event-driven (frankie_box_wake.py); a given value is ignored
set -- --line "$LINE" --code-root "$CODE_ROOT" --commit "$MARKETS_SHA"
case "$ACTION" in worker|kick|handover)
  : "${SCOPE:?SCOPE=RUN:YYYYMMDD,... (the authorized run and days) required}"
  case "$SCOPE" in *[!A-Za-z0-9_:,-]*) echo "SCOPE carries a character outside [A-Za-z0-9_:,-]" >&2; exit 2;; esac
  set -- "$@" --scope "$SCOPE" ;;
esac
case "$ACTION" in
  worker)
    # 2026-10-09: no worker lifetime limit unless MAX_SECONDS opts in (0 = none)
    case "${MAX_SECONDS:-0}" in ""|*[!0-9]*) echo "MAX_SECONDS must be whole seconds" >&2; exit 2;; esac
    exec "$PY" -B "$SCRIPT" --action worker "$@" --max-seconds "${MAX_SECONDS:-0}" ;;
  kick)
    # 2026-10-09: the kicked worker has no lifetime limit unless MAX_SECONDS opts in (FRANKIE_QUEUE_MAX_SECONDS)
    case "${MAX_SECONDS:-0}" in ""|*[!0-9]*) echo "MAX_SECONDS must be whole seconds" >&2; exit 2;; esac
    [ "${MAX_SECONDS:-0}" = 0 ] || export FRANKIE_QUEUE_MAX_SECONDS="$MAX_SECONDS"
    exec "$PY" -B "$SCRIPT" --action kick "$@" --max-seconds "${MAX_SECONDS:-0}" ;;
  handover)
    # the root line to this commit without stopping a running day: the old worker stops TAKING work (SIGTERM), finishes
    # the days in its slots and ends; a new worker at this commit waits on the lock and takes over (2026-09-30)
    case "${MAX_SECONDS:-0}" in ""|*[!0-9]*) echo "MAX_SECONDS must be whole seconds" >&2; exit 2;; esac
    [ "${MAX_SECONDS:-0}" = 0 ] || export FRANKIE_QUEUE_MAX_SECONDS="$MAX_SECONDS"
    exec "$PY" -B "$SCRIPT" --action handover "$@" --max-seconds "${MAX_SECONDS:-0}" ;;
  enqueue)
    : "${RUN:?the orchestrator run name required}"; : "${DAY:?YYYYMMDD required}"
    case "$RUN" in ""|*[!A-Za-z0-9_-]*) echo "RUN: letters, digits, _ and - only" >&2; exit 2;; esac
    case "$DAY" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) echo "DAY must be YYYYMMDD" >&2; exit 2;; esac
    case "${KICK:-on}" in on|off) ;; *) echo "KICK must be on or off" >&2; exit 2;; esac
    exec "$PY" -B "$SCRIPT" --action enqueue "$@" --run "$RUN" --day "$DAY" --kick "${KICK:-on}" ;;
esac
