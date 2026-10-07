# Stage 10: the survivor/candidate update at a cross-day batch boundary (frankie_box_survivor_update.py; Greg, 2026-10-07).
# Every tested claim one candidate, every test listed with its provenance, days named per mark, nothing averaged; filed
# immediately as the brain entry <BRAIN>/<BOUNDARY_DAY>-survivors for LATER classrooms only. Code only; no model call.
# Inputs: CODE_ROOT (staged checkout), RUN, BOUNDARY_DAY (the batch's last day), BATCH_DAYS (comma list, one or more days,
# the boundary day among them), BRAIN (default /opt/frankie-box/brain), OUT (default /opt/frankie-box/work/experiment-survivors),
# SEARCHES (optional: comma list of DAY=DIR completed search directories; default experiment-search/<day>/cycle-00/discovery).
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"; : "${CODE_ROOT:?staged clean checkout required}"
: "${RUN:?the orchestrator run name required}"; : "${BOUNDARY_DAY:?YYYYMMDD required}"; : "${BATCH_DAYS:?comma list of the batch days required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
case "$BOUNDARY_DAY" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) echo "BOUNDARY_DAY must be YYYYMMDD" >&2; exit 2;; esac
case "$RUN" in ""|*[!A-Za-z0-9_-]*) echo "RUN: letters, digits, _ and - only" >&2; exit 2;; esac
case "$BATCH_DAYS" in *[!0-9,]*) echo "BATCH_DAYS must be a comma list of YYYYMMDD days" >&2; exit 2;; esac
BRAIN="${BRAIN:-/opt/frankie-box/brain}"
case "$BRAIN" in /opt/frankie-box/*) ;; *) echo "BRAIN must be under /opt/frankie-box" >&2; exit 2;; esac
case "$BRAIN" in *..*) echo "no .. in BRAIN" >&2; exit 2;; esac
OUT="${OUT:-/opt/frankie-box/work/experiment-survivors}"
case "$OUT" in /opt/frankie-box/work/*) ;; *) echo "OUT must be under /opt/frankie-box/work" >&2; exit 2;; esac
case "$OUT" in *..*) echo "no .. in OUT" >&2; exit 2;; esac
set -- --run "$RUN" --boundary-day "$BOUNDARY_DAY" --days "$BATCH_DAYS" --brain "$BRAIN" --out-dir "$OUT"
for item in $(echo "${SEARCHES:-}" | tr ',' ' '); do
  case "$item" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]=/opt/frankie-box/work/experiment-search/*) set -- "$@" --search "$item";;
    *) echo "SEARCHES items must be DAY=<dir under experiment-search>: $item" >&2; exit 2;; esac
done
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
exec nice -n 10 /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_survivor_update.py" "$@"
