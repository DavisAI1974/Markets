# Per-day facts of candidate Tue/Wed trading days and the staged BLOCK manifests they need (frankie_box_day_facts.py;
# research/kalshi/frankie_boss/DAY_SELECTION_20260929.md). Read-only on everything that exists: it writes only new
# partition files under /opt/frankie-box/data/block_<block>/ (sha256-checked against the committed canonical manifest,
# never over a different file) and a fresh /opt/frankie-box/work/day-facts/<RUN>/. No ingest, no S3 write, no model
# call, nothing touches Databento.
# Inputs: CODE_ROOT (a checkout whose HEAD is MARKETS_SHA: /opt/frankie-box/code/* after frankie_box_stage_code.sh, or an
# ingest worktree /opt/frankie-box/ingest-code/<sha>), DAYS (comma list YYYYMMDD, Tue-Fri), RUN (fresh name),
# WORKERS (default 6, run under nice), CONFIRMATION (refuse | staging-only; default refuse: see the .py docstring),
# MAP_URL (frankie_box_run.yml presign=<bucket>/<key> for every partition; without it only partitions already on the box
# are used, the rest listed). Output: /opt/frankie-box/work/day-facts/<RUN>/{days,blocks,receipt.json}, all also printed.
# A probe: frankie_box_read_log.sh MODE=tail FILE=work/day-facts/<RUN>/receipt.json.
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"; : "${CODE_ROOT:?checkout at MARKETS_SHA required}"
: "${DAYS:?comma list of trading days required}"; : "${RUN:?fresh run name required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*|/opt/frankie-box/ingest-code/*) ;; *) echo "CODE_ROOT must be under /opt/frankie-box/code or /opt/frankie-box/ingest-code" >&2; exit 2;; esac
case "$CODE_ROOT$RUN$DAYS" in *..*) echo "no .. in CODE_ROOT, RUN or DAYS" >&2; exit 2;; esac
case "$RUN" in *[!A-Za-z0-9_-]*) echo "RUN must be [A-Za-z0-9_-]" >&2; exit 2;; esac
case "$DAYS" in *[!0-9,]*) echo "DAYS must be YYYYMMDD values separated by commas" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "CODE_ROOT differs from MARKETS_SHA" >&2; exit 2; }
WORKERS="${WORKERS:-6}"; CONFIRMATION="${CONFIRMATION:-refuse}"
case "$WORKERS" in ""|*[!0-9]*) echo "WORKERS must be an integer" >&2; exit 2;; esac
case "$CONFIRMATION" in refuse|staging-only) ;; *) echo "CONFIRMATION must be refuse or staging-only" >&2; exit 2;; esac
mkdir -p /opt/frankie-box/tmp
MAPF=""
if [ -n "${MAP_URL:-}" ]; then
  case "$MAP_URL" in https://*.amazonaws.com/*) ;; *) echo "MAP_URL must be an https amazonaws URL" >&2; exit 2;; esac
  MAPF="/opt/frankie-box/tmp/day-facts-map-$$.json"     # per dispatch; removed on exit
  trap 'rm -f "$MAPF"' EXIT
  curl -fsS --proto =https -m 60 --retry 3 -o "$MAPF" --url "$MAP_URL" || { echo "map download failed" >&2; exit 2; }
fi
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT:$CODE_ROOT/research/kalshi/frankie_boss"
set -- --code-root "$CODE_ROOT" --days "$DAYS" --run "$RUN" --workers "$WORKERS" --confirmation "$CONFIRMATION"
[ -z "$MAPF" ] || set -- "$@" --map "$MAPF"
nice -n 10 /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_day_facts.py" "$@"
