# The experiment's classroom arm for one day (frankie_box_experiment_classroom.py): the package from the teacher-only
# step's attachment, Frankie's code answers, the host's grade and correction, the completion, and Frankie's brain entry.
# No model, no Pod, no Granite. Inputs: CODE_ROOT (staged checkout), DAY (YYYYMMDD), CALCULATIONS (the day's experiment
# ROOT, run with DIGEST=on, under /opt/frankie-box/work/experiment-roots/), TEACHER_ROWS (default
# /opt/frankie-box/work/experiment-teacher-rows/<DAY>), PREVIOUS (optional: the previous classroom day's
# <root>/work/classroom, its history and grade carried in), BRAIN (default /opt/frankie-box/brain).
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"; : "${CODE_ROOT:?staged clean checkout required}"
: "${DAY:?YYYYMMDD required}"; : "${CALCULATIONS:?the experiment ROOT of the day required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
case "$DAY" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) echo "DAY must be YYYYMMDD" >&2; exit 2;; esac
TEACHER_ROWS="${TEACHER_ROWS:-/opt/frankie-box/work/experiment-teacher-rows/$DAY}"; BRAIN="${BRAIN:-/opt/frankie-box/brain}"
case "$CALCULATIONS" in /opt/frankie-box/work/experiment-roots/*) ;; *) echo "CALCULATIONS under /opt/frankie-box/work/experiment-roots required" >&2; exit 2;; esac
case "$TEACHER_ROWS" in /opt/frankie-box/work/experiment-teacher-rows/*) ;; *) echo "TEACHER_ROWS under experiment-teacher-rows required" >&2; exit 2;; esac
case "${PREVIOUS:-}" in ""|/opt/frankie-box/work/experiment-roots/*/work/classroom) ;; *) echo "PREVIOUS must be an experiment root's work/classroom" >&2; exit 2;; esac
case "$CALCULATIONS$TEACHER_ROWS${PREVIOUS:-}$BRAIN" in *..*) echo "no .. in paths" >&2; exit 2;; esac
set -- --day "$DAY" --calculations "$CALCULATIONS" --teacher-rows "$TEACHER_ROWS" --brain "$BRAIN"
[ -z "${PREVIOUS:-}" ] || set -- "$@" --previous "$PREVIOUS"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_experiment_classroom.py" "$@"
