# The scientific teacher's turn (frankie_box_scientific_teacher.py): Jev's and Frankie's claims tested on the search's
# counts, each discovery day on its own, and their lessons written (Jev's uploaded to his brain on S3 through the
# presigned slot). Code only; no model call. Inputs: CODE_ROOT, SEARCHES (space-free, comma-separated discovery-day
# search directories), and JEV_STAMP (with presign getprefix:.../clm-sidecar/<stamp>/jev/ and
# put:.../clm-sidecar/jev-brain/lessons/<day>-<stamp>.json) and/or FRANKIE_LEDGERS + FRANKIE_DAY and/or HISTORICAL_CLAIMS
# (a committed research/kalshi/frankie_boss/knowledge/HISTORICAL_CLAIMS_V1-*.json, relative to the staged checkout).
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"; : "${CODE_ROOT:?staged clean checkout required}"; : "${SEARCHES:?search directories required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
BRAIN="${BRAIN:-/opt/frankie-box/brain}"
case "$BRAIN" in /opt/frankie-box/*) ;; *) echo "BRAIN must be under /opt/frankie-box" >&2; exit 2;; esac
case "$BRAIN" in *..*) echo "no .. in BRAIN" >&2; exit 2;; esac
set -- --brain "$BRAIN"
for d in $(echo "$SEARCHES" | tr ',' ' '); do
  case "$d" in /opt/frankie-box/work/experiment-search/*) set -- "$@" --search "$d";; *) echo "search directory under experiment-search required: $d" >&2; exit 2;; esac
done
if [ -n "${ACCUMULATED_DAY:-}" ] || [ -n "${ACCUMULATED_OUT:-}" ]; then
  : "${ACCUMULATED_DAY:?owning day required}"; : "${ACCUMULATED_OUT:?retained accumulated result directory required}"
  case "$ACCUMULATED_OUT" in /opt/frankie-box/work/experiment/*/scientific-knowledge/*) ;; *) echo "accumulated result must stay in the owning experiment" >&2; exit 2;; esac
  case "$ACCUMULATED_OUT" in *..*) echo "no .. in accumulated result directory" >&2; exit 2;; esac
  set -- "$@" --accumulated-day "$ACCUMULATED_DAY" --accumulated-out "$ACCUMULATED_OUT"
fi
[ -z "${JEV_STAMP:-}" ] || set -- "$@" --jev-stamp "$JEV_STAMP"
[ -z "${FRANKIE_LEDGERS:-}" ] || set -- "$@" --frankie-ledgers "$FRANKIE_LEDGERS" --frankie-day "${FRANKIE_DAY:?FRANKIE_DAY required}"
if [ -n "${SEARCH_FINDINGS:-}" ]; then
  # one day's knowledge-findings.json (FRANKIE_SEARCH_FINDINGS_V1), beside its search MANIFEST; tested on the other searches
  case "$SEARCH_FINDINGS" in /opt/frankie-box/work/experiment-search/*/knowledge-findings.json) ;; *) echo "SEARCH_FINDINGS must be a knowledge-findings.json under experiment-search" >&2; exit 2;; esac
  case "$SEARCH_FINDINGS" in *..*) echo "no .. in SEARCH_FINDINGS" >&2; exit 2;; esac
  set -- "$@" --search-findings "$SEARCH_FINDINGS"
fi
if [ -n "${HISTORICAL_CLAIMS:-}" ]; then
  case "$HISTORICAL_CLAIMS" in research/kalshi/frankie_boss/knowledge/HISTORICAL_CLAIMS_V1-*.json) ;; *) echo "HISTORICAL_CLAIMS must be a committed knowledge/HISTORICAL_CLAIMS_V1 file" >&2; exit 2;; esac
  set -- "$@" --historical-claims "$CODE_ROOT/$HISTORICAL_CLAIMS"
fi
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT" MAP_URL="${MAP_URL:-}"
exec nice -n 10 /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_scientific_teacher.py" "$@"
