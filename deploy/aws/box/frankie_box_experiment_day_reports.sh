# The experiment's day reports (frankie_box_experiment_day_reports.py; Greg, 2026-09-29: "make sure classroom is printing
# out an analysis after every day has gone through it, and same with Frankie, and have them number their reports";
# "There will be (3) #1's and so on"; "Write plain language interpreters to their code"): for ONE classroom day, reads
# the classroom's outputs (read-only) and the brain entry its receipt names, and writes CLASSROOM REPORT #N and FRANKIE
# REPORT #N (one number per trade day, shared with that day's JEV REPORT #N; fixed plain-English templates of the
# recorded fields, no interpretation) into REPORTS_DIR and the classroom dir, printing both in full; the last two lines
# are REPORT_NUMBER=N and the receipt JSON. No model, no Pod, no Granite. Inputs: CODE_ROOT (staged checkout), DAY
# (YYYYMMDD), CLASSROOM (<root>/work/classroom under /opt/frankie-box/work/experiment-roots/), RUN (the orchestrator run
# name), REPORTS_DIR (default /opt/frankie-box/work/experiment-reports), DAY_CLASS (optional; default from the weekday),
# REFUSED_REASON (optional: the orchestrator's reason when it refused the classroom before a receipt was written),
# EXCHANGE (optional: the day's exchange.json under /opt/frankie-box/work/experiment/<run>/exchange/<day>/; both
# reports carry the three-way exchange), EXCHANGE_LISTED (optional: why there is none), SCHOOL (optional, 2026-10-07: the
# day's FRANKIE_SCHOOL_KNOWLEDGE_V1 file the school stage wrote, <brain>/school/<day>.json or a retained checked successor
# <brain>/school/successors/<day>/<op>/school.json; the FRANKIE report carries what it consolidated and what it lists
# missing or withheld; its sha256 is part of the reports' source), SCHOOL_LISTED (optional: why there is none).
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"; : "${CODE_ROOT:?staged clean checkout required}"
: "${DAY:?YYYYMMDD required}"; : "${CLASSROOM:?the classroom directory of the day required}"; : "${RUN:?the orchestrator run name required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
case "$DAY" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) echo "DAY must be YYYYMMDD" >&2; exit 2;; esac
case "$RUN" in ""|*[!A-Za-z0-9_-]*) echo "RUN: letters, digits, _ and - only" >&2; exit 2;; esac
REPORTS_DIR="${REPORTS_DIR:-/opt/frankie-box/work/experiment-reports}"
case "$CLASSROOM" in /opt/frankie-box/work/experiment-roots/*/work/classroom) ;; *) echo "CLASSROOM must be an experiment root's work/classroom" >&2; exit 2;; esac
case "$REPORTS_DIR" in /opt/frankie-box/work/*) ;; *) echo "REPORTS_DIR must be under /opt/frankie-box/work" >&2; exit 2;; esac
case "$CLASSROOM$REPORTS_DIR" in *..*) echo "no .. in paths" >&2; exit 2;; esac
case "${DAY_CLASS:-}" in ""|monday|midweek|thursday|friday) ;; *) echo "DAY_CLASS must be monday, midweek, thursday or friday" >&2; exit 2;; esac
set -- --day "$DAY" --classroom "$CLASSROOM" --run "$RUN" --reports-dir "$REPORTS_DIR"
[ -z "${DAY_CLASS:-}" ] || set -- "$@" --day-class "$DAY_CLASS"
[ -z "${REFUSED_REASON:-}" ] || set -- "$@" --refused-reason "$REFUSED_REASON"
case "${EXCHANGE:-}" in ""|/opt/frankie-box/work/experiment/*/exchange/[0-9]*/exchange.json) ;; *) echo "EXCHANGE must be an orchestrator run's exchange/<day>/exchange.json" >&2; exit 2;; esac
case "${EXCHANGE:-}" in *..*) echo "no .. in EXCHANGE" >&2; exit 2;; esac
[ -z "${EXCHANGE:-}" ] || set -- "$@" --exchange "$EXCHANGE"
[ -z "${EXCHANGE_LISTED:-}" ] || set -- "$@" --exchange-listed "$EXCHANGE_LISTED"
case "${SCHOOL:-}" in ""|/opt/frankie-box/*/school/[0-9]*.json|/opt/frankie-box/*/school/successors/[0-9]*/*/school.json) ;; *) echo "SCHOOL must be a brain's school/<day>.json or school/successors/<day>/<operation>/school.json" >&2; exit 2;; esac
case "${SCHOOL:-}" in *..*) echo "no .. in SCHOOL" >&2; exit 2;; esac
[ -z "${SCHOOL:-}" ] || set -- "$@" --school "$SCHOOL"
[ -z "${SCHOOL_LISTED:-}" ] || set -- "$@" --school-listed "$SCHOOL_LISTED"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_experiment_day_reports.py" "$@"
