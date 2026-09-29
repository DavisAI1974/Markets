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
# LAGS, TRANSFORMS, INGEST_WORKERS (31), DATA_WORKERS (1), SEARCH_WORKERS (8), TEACHER_CPUS (0 = every core), PARALLEL_DAYS (4), DISK_FLOOR_GB (100),
# EXTERNAL_HISTORY_RUN (the day_history run id the day files are built from), EXTERNAL_HISTORY_EIA930_RUN (optional
# second run id for the eia930 family), EXTERNAL_HISTORY_FAMILY_RUNS (optional family=<run id>,...), EXTERNAL_WAIT (on|off), BRAIN,
# PREVIOUS_CLASSROOM (the run's first arm day), MAP_URL (the dispatch's presigned map: the partitions for fetch, the
# day history and curve prefixes and the day-file slots for external, Jev's material slots for jev; ACTION=plan prints
# the whole presign string). A probe: frankie_box_progress.sh
# DIRECTORY=/opt/frankie-box/work/experiment/<RUN>.
set -eu
export HOME="${HOME:-/root}"   # SSM runs without HOME; DuckDB refuses to load extensions without a home directory (2026-09-29)
: "${MARKETS_SHA:?full dispatched commit required}"; : "${CODE_ROOT:?staged clean checkout required}"; : "${RUN:?run name required}"
ACTION="${ACTION:-plan}"
case "$ACTION" in plan|start|status) ;; *) echo "ACTION must be plan, start or status" >&2; exit 2;; esac
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
set -- --action "$ACTION" --run "$RUN" --commit "$MARKETS_SHA" --code-root "$CODE_ROOT"
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
case "${BRAIN:-/opt/frankie-box/brain}${PREVIOUS_CLASSROOM:-}" in *..*) echo "no .. in BRAIN or PREVIOUS_CLASSROOM" >&2; exit 2;; esac
case "${BRAIN:-/opt/frankie-box/brain}" in /opt/frankie-box/*) ;; *) echo "BRAIN must be under /opt/frankie-box" >&2; exit 2;; esac
case "${PREVIOUS_CLASSROOM:-}" in ""|/opt/frankie-box/work/experiment-roots/*/work/classroom) ;; *) echo "PREVIOUS_CLASSROOM must be an experiment root's work/classroom" >&2; exit 2;; esac
[ -z "${PREVIOUS_CLASSROOM:-}" ] || set -- "$@" --previous-classroom "$PREVIOUS_CLASSROOM"
set -- "$@" --lags "${LAGS:-20}" --ingest-workers "${INGEST_WORKERS:-31}" --data-workers "${DATA_WORKERS:-1}" \
  --search-workers "${SEARCH_WORKERS:-8}" --teacher-cpus "${TEACHER_CPUS:-0}" --parallel-days "${PARALLEL_DAYS:-4}" --disk-floor-gb "${DISK_FLOOR_GB:-100}"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT" MAP_URL="${MAP_URL:-}"
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_experiment.py" "$@"
