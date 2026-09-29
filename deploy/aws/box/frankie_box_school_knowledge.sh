# Frankie's SCHOOL KNOWLEDGE BASE for ONE classroom-arm day (frankie_box_school_knowledge.py; Greg, 2026-09-29): ONE JSON
# file FRANKIE_SCHOOL_KNOWLEDGE_V1 at <BRAIN>/school/<DAY>.json plus its row in the append-only <BRAIN>/school/index.json
# (day, file, sha256, bytes, report number N). Sections labelled with their authors (R11): frankie_classwork,
# boss_teacher, scientific_teacher, exchange, day_file; every item with its source path and sha256; never the answer key
# or the exhaustive grade (R10); missing listed with the reason. Code only; no model call. Monday 20211004 is refused
# (out of the school). Inputs: CODE_ROOT (staged checkout), DAY, RUN, REPORT_NUMBER (the day's N), CLASSROOM (the day's
# <root>/work/classroom), EXCHANGE_VIEW (optional: the exchange's exchange-frankie.json), EXCHANGE_LISTED (optional: why
# there is none), LESSONS (optional: the day's FRANKIE_LESSONS_V1), TEACHER_ROWS (optional: experiment-teacher-rows/<DAY>),
# BRAIN (default /opt/frankie-box/brain), SCHOOL_DAY (optional: the day's number in Frankie's class line, equal to
# REPORT_NUMBER; kept in the school row).
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"; : "${CODE_ROOT:?staged clean checkout required}"
: "${DAY:?YYYYMMDD required}"; : "${RUN:?the orchestrator run name required}"; : "${REPORT_NUMBER:?the report number of the day required}"
: "${CLASSROOM:?the classroom directory of the day required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
case "$DAY" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) echo "DAY must be YYYYMMDD" >&2; exit 2;; esac
case "$RUN" in ""|*[!A-Za-z0-9_-]*) echo "RUN: letters, digits, _ and - only" >&2; exit 2;; esac
case "$REPORT_NUMBER" in ""|*[!0-9]*) echo "REPORT_NUMBER must be a number" >&2; exit 2;; esac
case "${SCHOOL_DAY:-}" in *[!0-9]*) echo "SCHOOL_DAY must be a number" >&2; exit 2;; esac
case "$CLASSROOM" in /opt/frankie-box/work/experiment-roots/*/work/classroom) ;; *) echo "CLASSROOM must be an experiment root's work/classroom" >&2; exit 2;; esac
case "${EXCHANGE_VIEW:-}" in ""|/opt/frankie-box/work/experiment/*/exchange/[0-9]*/exchange-frankie.json) ;; *) echo "EXCHANGE_VIEW must be an orchestrator run's exchange/<day>/exchange-frankie.json" >&2; exit 2;; esac
case "${LESSONS:-}" in ""|/opt/frankie-box/work/experiment-teacher/frankie/*.json) ;; *) echo "LESSONS must be a FRANKIE_LESSONS_V1 under experiment-teacher/frankie" >&2; exit 2;; esac
case "${TEACHER_ROWS:-}" in ""|/opt/frankie-box/work/*) ;; *) echo "TEACHER_ROWS must be under /opt/frankie-box/work" >&2; exit 2;; esac
BRAIN="${BRAIN:-/opt/frankie-box/brain}"
case "$BRAIN" in /opt/frankie-box/*) ;; *) echo "BRAIN must be under /opt/frankie-box" >&2; exit 2;; esac
case "$CLASSROOM$BRAIN${EXCHANGE_VIEW:-}${LESSONS:-}${TEACHER_ROWS:-}" in *..*) echo "no .. in paths" >&2; exit 2;; esac
set -- --day "$DAY" --run "$RUN" --report-number "$REPORT_NUMBER" --classroom "$CLASSROOM" --brain "$BRAIN"
[ -z "${EXCHANGE_VIEW:-}" ] || set -- "$@" --exchange-view "$EXCHANGE_VIEW"
[ -z "${EXCHANGE_LISTED:-}" ] || set -- "$@" --exchange-listed "$EXCHANGE_LISTED"
[ -z "${LESSONS:-}" ] || set -- "$@" --lessons "$LESSONS"
[ -z "${TEACHER_ROWS:-}" ] || set -- "$@" --teacher-rows "$TEACHER_ROWS"
[ -z "${SCHOOL_DAY:-}" ] || set -- "$@" --school-day "$SCHOOL_DAY"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
exec nice -n 10 /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_school_knowledge.py" "$@"
