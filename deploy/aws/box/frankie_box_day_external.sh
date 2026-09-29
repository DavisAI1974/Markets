# Frankie's 13 points attached to each trading day (frankie_box_day_external.py; the builder and the one as-of reader are
# research/kalshi/frankie_boss/operations/frankie_day_external.py). ACTION=build fetches the day's inputs through the
# presigned map, builds day-external.json + its receipt per day under /opt/frankie-box/work/day-external/<RUN>/<day>/,
# and attaches them: hard links beside the day's sealed ingest, the S3 day key through presigned PUT slots, a listed
# attachment in the brain (<BRAIN>/<day>-external/). ACTION=link attaches an existing RUN again (after an ingest seals).
# Inputs: CODE_ROOT (a checkout whose HEAD is MARKETS_SHA: /opt/frankie-box/code/* or /opt/frankie-box/ingest-code/*),
# DAYS (comma list YYYYMMDD), RUN (fresh for build), HISTORY_RUN (the day_history GitHub run id), EIA930_HISTORY_RUN
# (optional: a second day_history run id the eia930 family is read from), HISTORY_FAMILY_RUNS (optional family=<run id>,...
# for families read from other day_history runs), MAP_URL (build:
# frankie_box_run.yml presign), BRAIN (optional, under /opt/frankie-box), WORKERS (default 2, days side by side).
# No ingest, no journal or receipt of the ingest edited, no pinned file touched, no model call; the box writes nothing to
# S3 except through the presigned slots it is handed. SSM runs this under sh: POSIX only.
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"; : "${CODE_ROOT:?checkout at MARKETS_SHA required}"
: "${DAYS:?comma list of trading days required}"; : "${RUN:?run name required}"; : "${HISTORY_RUN:?day_history run id required}"
ACTION="${ACTION:-build}"; WORKERS="${WORKERS:-2}"; BRAIN="${BRAIN:-}"
case "$ACTION" in build|link) ;; *) echo "ACTION must be build or link" >&2; exit 2;; esac
case "$CODE_ROOT" in /opt/frankie-box/code/*|/opt/frankie-box/ingest-code/*) ;; *) echo "CODE_ROOT must be under /opt/frankie-box/code or /opt/frankie-box/ingest-code" >&2; exit 2;; esac
case "$CODE_ROOT$RUN$DAYS$BRAIN" in *..*) echo "no .. in CODE_ROOT, RUN, DAYS or BRAIN" >&2; exit 2;; esac
case "$RUN" in *[!A-Za-z0-9_-]*) echo "RUN must be [A-Za-z0-9_-]" >&2; exit 2;; esac
case "$DAYS" in *[!0-9,]*) echo "DAYS must be YYYYMMDD values separated by commas" >&2; exit 2;; esac
case "$HISTORY_RUN" in ""|*[!0-9]*) echo "HISTORY_RUN must be the numeric GitHub run id" >&2; exit 2;; esac
EIA930_HISTORY_RUN="${EIA930_HISTORY_RUN:-}"
case "$EIA930_HISTORY_RUN" in *[!0-9]*) echo "EIA930_HISTORY_RUN must be the numeric GitHub run id" >&2; exit 2;; esac
HISTORY_FAMILY_RUNS="${HISTORY_FAMILY_RUNS:-}"
case "$HISTORY_FAMILY_RUNS" in *[!a-z0-9_=,]*) echo "HISTORY_FAMILY_RUNS must be family=<run id>,..." >&2; exit 2;; esac
case "$WORKERS" in ""|*[!0-9]*) echo "WORKERS must be an integer" >&2; exit 2;; esac
case "$BRAIN" in ""|/opt/frankie-box/*) ;; *) echo "BRAIN must be under /opt/frankie-box" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "CODE_ROOT differs from MARKETS_SHA" >&2; exit 2; }
mkdir -p /opt/frankie-box/tmp
MAPF=""
if [ -n "${MAP_URL:-}" ]; then
  case "$MAP_URL" in https://*.amazonaws.com/*) ;; *) echo "MAP_URL must be an https amazonaws URL" >&2; exit 2;; esac
  MAPF="/opt/frankie-box/tmp/day-external-map-$$.json"
  trap 'rm -f "$MAPF"' EXIT
  curl -fsS --proto =https -m 60 --retry 3 -o "$MAPF" --url "$MAP_URL" || { echo "map download failed" >&2; exit 2; }
elif [ "$ACTION" = build ]; then
  echo "ACTION=build needs MAP_URL (frankie_box_run.yml presign)" >&2; exit 2
fi
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT:$CODE_ROOT/research/kalshi:$CODE_ROOT/research/kalshi/frankie_boss"
set -- --action "$ACTION" --code-root "$CODE_ROOT" --markets-sha "$MARKETS_SHA" --days "$DAYS" --run "$RUN" \
  --history-run "$HISTORY_RUN" --workers "$WORKERS"
[ -z "$MAPF" ] || set -- "$@" --map "$MAPF"
[ -z "$EIA930_HISTORY_RUN" ] || set -- "$@" --eia930-history-run "$EIA930_HISTORY_RUN"
[ -z "$HISTORY_FAMILY_RUNS" ] || set -- "$@" --family-history-runs "$HISTORY_FAMILY_RUNS"
[ -z "$BRAIN" ] || set -- "$@" --brain "$BRAIN"
nice -n 10 /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_day_external.py" "$@"
