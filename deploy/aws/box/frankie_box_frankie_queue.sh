# Frankie's FIFO queue (frankie_box_frankie_queue.py; Greg, 2026-09-29: "I don't want any days dropped and moved forward
# because he was busy"; "order by first in the pod first out the pod or box"; "And the root calcs too"; "Class days are
# sequential"). Two lines under /opt/frankie-box/work/frankie-queue/, each arrival-order FIFO (enqueued_at then a
# monotonic seq): the ROOT line (a day enters when its sealed ingest and day file are there; days leave in arrival order
# to the next free day-run slot, box or Pod) and the CLASS line (an arm day enters when its ROOT, teacher rows and day file
# are there; ONE class at a time, school day = position in the line = report number N, each class carrying the last class
# to finish). Nothing dropped, skipped or reordered. No model call, no Pod call, no Granite, no Databento.
# Inputs: CODE_ROOT (staged checkout), ACTION:
#   show                         read-only: both lines, every entry with its state and reason, the workers [EVENTS=50|all]
#   enqueue LINE RUN DAY         the orchestrator's own readiness checks on the run's saved plan, then the entry [KICK=on]
#   worker  LINE                 the line's one worker in the foreground, bounded [MAX_SECONDS=1500 POLL_SECONDS=60]; a
#                                second worker exits at once; exit 0 idle, 3 stopped at a failed entry, 5 saved at the bound
#   kick    LINE                 starts the line's worker detached (systemd-run) unless one runs [MAX_SECONDS=43200]
#   handover LINE=root           the running worker stops taking work and ends after its running days; a new worker at
#                                this commit (every day runs its whole day in its slot) waits on the lock and takes over
#   save    RUN DAY              the day-bound save of a running owned day: its marker written; the owner stops at its
#                                next boundary (a class in progress acknowledges first); acknowledgment pending = status
#   status  RUN DAY              read-only: the owner binding, marker, class acknowledgment, ledger booking (live /
#                                retained / released), both line entries and the worker, distinctly
#   resume  RUN DAY              a saved/unknown owned day back in line with the SAME owner (attempt, CPUs, marker
#                                archived); then kick LINE=root (SCOPE=RUN:DAY) so the next admission takes it
# LINE is root or class. MARKETS_SHA (the dispatched commit) is required for every action but show and status.
set -eu
export HOME="${HOME:-/root}"
: "${CODE_ROOT:?staged checkout required}"
ACTION="${ACTION:-show}"
case "$ACTION" in show|enqueue|worker|kick|handover|save|status|resume) ;; *) echo "ACTION must be show, enqueue, worker, kick, handover, save, status or resume" >&2; exit 2;; esac
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
case "$CODE_ROOT" in *..*) echo "no .. in CODE_ROOT" >&2; exit 2;; esac
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
PY=/opt/frankie-box/venv/bin/python
SCRIPT="$CODE_ROOT/deploy/aws/box/frankie_box_frankie_queue.py"
if [ "$ACTION" = show ]; then
  case "${EVENTS:-50}" in all) ;; ""|*[!0-9]*) echo "EVENTS must be a number or all" >&2; exit 2;; esac
  exec "$PY" -B "$SCRIPT" --action show --events "${EVENTS:-50}"
fi
case "$ACTION" in save|status|resume)
  : "${RUN:?the orchestrator run name required}"; : "${DAY:?YYYYMMDD required}"
  case "$RUN" in ""|*[!A-Za-z0-9_-]*) echo "RUN: letters, digits, _ and - only" >&2; exit 2;; esac
  case "$DAY" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) echo "DAY must be YYYYMMDD" >&2; exit 2;; esac
  if [ "$ACTION" != status ]; then
    : "${MARKETS_SHA:?full dispatched commit required}"
    [ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
  fi
  exec "$PY" -B "$SCRIPT" --action "$ACTION" --run "$RUN" --day "$DAY" ;;
esac
: "${MARKETS_SHA:?full dispatched commit required}"
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
case "${LINE:-}" in root|class) ;; *) echo "LINE must be root or class" >&2; exit 2;; esac
case "${POLL_SECONDS:-60}" in ""|*[!0-9]*) echo "POLL_SECONDS must be whole seconds" >&2; exit 2;; esac
set -- --line "$LINE" --code-root "$CODE_ROOT" --commit "$MARKETS_SHA" --poll-seconds "${POLL_SECONDS:-60}"
case "$ACTION" in
  worker)
    case "${MAX_SECONDS:-1500}" in ""|*[!0-9]*) echo "MAX_SECONDS must be whole seconds" >&2; exit 2;; esac
    exec "$PY" -B "$SCRIPT" --action worker "$@" --max-seconds "${MAX_SECONDS:-1500}" ;;
  kick)
    case "${MAX_SECONDS:-43200}" in ""|*[!0-9]*) echo "MAX_SECONDS must be whole seconds" >&2; exit 2;; esac
    exec "$PY" -B "$SCRIPT" --action kick "$@" --max-seconds "${MAX_SECONDS:-43200}" ;;
  handover)
    # the root line to this commit without stopping a running day: the old worker stops TAKING work (SIGTERM), finishes
    # the days in its slots and ends; a new worker at this commit waits on the lock and takes over (2026-09-30)
    case "${MAX_SECONDS:-43200}" in ""|*[!0-9]*) echo "MAX_SECONDS must be whole seconds" >&2; exit 2;; esac
    exec "$PY" -B "$SCRIPT" --action handover "$@" --max-seconds "${MAX_SECONDS:-43200}" ;;
  enqueue)
    : "${RUN:?the orchestrator run name required}"; : "${DAY:?YYYYMMDD required}"
    case "$RUN" in ""|*[!A-Za-z0-9_-]*) echo "RUN: letters, digits, _ and - only" >&2; exit 2;; esac
    case "$DAY" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) echo "DAY must be YYYYMMDD" >&2; exit 2;; esac
    case "${KICK:-on}" in on|off) ;; *) echo "KICK must be on or off" >&2; exit 2;; esac
    exec "$PY" -B "$SCRIPT" --action enqueue "$@" --run "$RUN" --day "$DAY" --kick "${KICK:-on}" ;;
esac
