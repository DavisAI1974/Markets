# The experiment orchestrator (frankie_box_experiment.py; SPEC-experiment-orchestrator.md "How the orchestrator runs"):
# one run over a list of days of ONE class, calling the committed steps in order (fetch, ingest, root, teacher, data,
# search, lessons), a receipt per day and step under /opt/frankie-box/work/experiment/<RUN>/, resume on restart, a stop
# and save at the disk floor. No model call, no Granite, no Pod.
# Inputs: CODE_ROOT (staged checkout), ACTION (plan | start | status; default plan, read-only), RUN (the run name),
# DAYS (comma list YYYYMMDD) and/or PLAN (a plan JSON, repo-relative or under /opt/frankie-box), DAY_CLASS (monday |
# midweek | thursday | friday), CLASSROOM_ARM (comma list), FROZEN_SURVIVORS (confirmation days only), HISTORICAL_CLAIMS
# (repo-relative committed file), WITHOUT_DIPOLE (1 to export and search days with no Dipole rows), STAGES (comma list),
# LAGS, TRANSFORMS, INGEST_WORKERS (31), DATA_WORKERS (1), SEARCH_WORKERS (8), PARALLEL_DAYS (4), DISK_FLOOR_GB (100),
# MAP_URL (the presigned partitions, for STAGES=fetch). A probe: frankie_box_progress.sh
# DIRECTORY=/opt/frankie-box/work/experiment/<RUN>.
set -eu
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
[ -z "${FROZEN_SURVIVORS:-}" ] || set -- "$@" --frozen-survivors "$FROZEN_SURVIVORS"
[ -z "${HISTORICAL_CLAIMS:-}" ] || set -- "$@" --historical-claims "$HISTORICAL_CLAIMS"
[ "${WITHOUT_DIPOLE:-0}" != 1 ] || set -- "$@" --without-dipole
[ -z "${STAGES:-}" ] || set -- "$@" --stages "$STAGES"
[ -z "${TRANSFORMS:-}" ] || set -- "$@" --transforms "$TRANSFORMS"
set -- "$@" --lags "${LAGS:-20}" --ingest-workers "${INGEST_WORKERS:-31}" --data-workers "${DATA_WORKERS:-1}" \
  --search-workers "${SEARCH_WORKERS:-8}" --parallel-days "${PARALLEL_DAYS:-4}" --disk-floor-gb "${DISK_FLOOR_GB:-100}"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT" MAP_URL="${MAP_URL:-}"
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_experiment.py" "$@"
