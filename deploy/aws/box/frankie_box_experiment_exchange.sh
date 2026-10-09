# The three-way exchange of ONE classroom-arm discovery day (frankie_box_experiment_exchange.py; SPEC-scientific-teacher.md
# step 5): the BOSS teacher's turn from its own Dipole rows, the scientific teacher's reply with the search's counts,
# Frankie's reply by his code; the teachers' own findings filed, scoped, their day named. Code only; no model call.
# Writes exchange.json, exchange-frankie.json and receipt.json into OUT_DIR and Frankie's view into his brain as
# <BRAIN>/<DAY>-exchange/. Inputs: CODE_ROOT (staged checkout), DAY (YYYYMMDD), RUN (the orchestrator run name), LESSONS
# (comma list of lessons files under /opt/frankie-box/work/experiment-teacher/ that tested the day), TEACHER_ROWS
# (optional: the day's host-dipole-classroom-source*.json), OUT_DIR (/opt/frankie-box/work/experiment/<RUN>/exchange/<DAY>),
# BRAIN (default /opt/frankie-box/brain).
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"; : "${CODE_ROOT:?staged clean checkout required}"
: "${DAY:?YYYYMMDD required}"; : "${RUN:?the orchestrator run name required}"; : "${OUT_DIR:?output directory required}"
LESSONS="${LESSONS:-}" # completed brain lessons may be the only exchange inputs
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
HEAD_SHA=$(git -C "$CODE_ROOT" rev-parse HEAD 2>/dev/null) || HEAD_SHA="${MARKETS_SHA:-}"  # 2026-10-09: recorded, never compared
[ "$HEAD_SHA" = "${MARKETS_SHA:-}" ] || { echo "code version: MARKETS_SHA ${MARKETS_SHA:-unset}, checkout $CODE_ROOT at $HEAD_SHA; this step runs on (and records) $HEAD_SHA" >&2; MARKETS_SHA=$HEAD_SHA; }
case "$DAY" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) echo "DAY must be YYYYMMDD" >&2; exit 2;; esac
case "$RUN" in ""|*[!A-Za-z0-9_-]*) echo "RUN: letters, digits, _ and - only" >&2; exit 2;; esac
case "$OUT_DIR" in "/opt/frankie-box/work/experiment/$RUN/exchange/$DAY") ;; *) echo "OUT_DIR must be /opt/frankie-box/work/experiment/<RUN>/exchange/<DAY>" >&2; exit 2;; esac
BRAIN="${BRAIN:-/opt/frankie-box/brain}"
case "$BRAIN" in /opt/frankie-box/*) ;; *) echo "BRAIN must be under /opt/frankie-box" >&2; exit 2;; esac
case "$BRAIN${TEACHER_ROWS:-}$LESSONS${SEARCH_DIR:-}" in *..*) echo "no .. in paths" >&2; exit 2;; esac
set -- --day "$DAY" --run "$RUN" --out-dir "$OUT_DIR" --brain "$BRAIN"
case "${SEARCH_DIR:-}" in
  /opt/frankie-box/work/experiment-search/"$DAY"/cycle-*/discovery) set -- "$@" --search "$SEARCH_DIR";;
  *) echo "SEARCH_DIR must be the owning day's completed discovery search" >&2; exit 2;;
esac
for f in $(echo "$LESSONS" | tr ',' ' '); do
  case "$f" in /opt/frankie-box/work/experiment-teacher/*.json) set -- "$@" --lessons "$f";; *) echo "lessons file under experiment-teacher required: $f" >&2; exit 2;; esac
done
case "${TEACHER_ROWS:-}" in ""|/opt/frankie-box/work/*host-dipole-classroom-source*.json) ;; *) echo "TEACHER_ROWS must be a host-dipole-classroom-source*.json under /opt/frankie-box/work" >&2; exit 2;; esac
[ -z "${TEACHER_ROWS:-}" ] || set -- "$@" --teacher-rows "$TEACHER_ROWS"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
exec nice -n 10 /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_experiment_exchange.py" "$@"
