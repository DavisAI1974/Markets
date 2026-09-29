# The scientific teacher's turn (frankie_box_scientific_teacher.py): Jev's and Frankie's claims tested on the search's
# counts, each discovery day on its own, and their lessons written (Jev's uploaded to his brain on S3 through the
# presigned slot). Code only; no model call. Inputs: CODE_ROOT, SEARCHES (space-free, comma-separated discovery-day
# search directories), and JEV_STAMP (with presign getprefix:.../clm-sidecar/<stamp>/jev/ and
# put:.../clm-sidecar/jev-brain/lessons/<day>-<stamp>.json) and/or FRANKIE_LEDGERS + FRANKIE_DAY.
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"; : "${CODE_ROOT:?staged clean checkout required}"; : "${SEARCHES:?search directories required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
set --
for d in $(echo "$SEARCHES" | tr ',' ' '); do
  case "$d" in /opt/frankie-box/work/experiment-search/*) set -- "$@" --search "$d";; *) echo "search directory under experiment-search required: $d" >&2; exit 2;; esac
done
[ -z "${JEV_STAMP:-}" ] || set -- "$@" --jev-stamp "$JEV_STAMP"
[ -z "${FRANKIE_LEDGERS:-}" ] || set -- "$@" --frankie-ledgers "$FRANKIE_LEDGERS" --frankie-day "${FRANKIE_DAY:?FRANKIE_DAY required}"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT" MAP_URL="${MAP_URL:-}"
exec nice -n 10 /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_scientific_teacher.py" "$@"
