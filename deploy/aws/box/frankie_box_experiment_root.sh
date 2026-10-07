# The experiment's ROOT for any ingested day (frankie_box_experiment_root.py): the day's sealed ingest read in place, the
# same whole-day pin, Session.derive with the NATIVE PASS ON for the experiment (Greg reversed the 2026-09-29 no-bedrock
# decision: every NEW run's plan carries SHARED_MARKET_POLICY, under which BEDROCK defaults to on below; only an older
# saved legacy plan, never mutated, still reaches here without a policy and keeps its native-off ROOT) (ROOT process 1
# always; process 4, the digest, with DIGEST=on). No authorship, no re-ingest, no model call. Inputs: CODE_ROOT, INGESTION_RECEIPT (the day's
# compact ingestion-receipt.json) + INGESTION_RECEIPT_SHA256, DAY (YYYYMMDD), DAY_ROLE (discovery | confirmation, the
# latter only with FROZEN_SURVIVORS), OUTPUT_ROOT (fresh, under /opt/frankie-box/work/experiment-roots/), DATA_WORKERS,
# DIGEST (on | off, default off). A probe: frankie_box_progress.sh DIRECTORY=<OUTPUT_ROOT>.
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"; : "${CODE_ROOT:?staged clean checkout required}"
: "${INGESTION_RECEIPT:?the ingestion receipt of the day required}"; : "${INGESTION_RECEIPT_SHA256:?its sha256 required}"
: "${DAY:?YYYYMMDD required}"; : "${DAY_ROLE:?discovery or confirmation required}"; : "${OUTPUT_ROOT:?fresh output root required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
case "$OUTPUT_ROOT" in /opt/frankie-box/work/experiment-roots/*) ;; *) echo "OUTPUT_ROOT under /opt/frankie-box/work/experiment-roots required" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
set -- --commit "$MARKETS_SHA" --ingestion-receipt "$INGESTION_RECEIPT" --ingestion-receipt-sha256 "$INGESTION_RECEIPT_SHA256" \
  --day "$DAY" --day-role "$DAY_ROLE" --output-root "$OUTPUT_ROOT" --data-workers "${DATA_WORKERS:-1}" --digest "${DIGEST:-off}"
# New shared-input requests select the versioned shared policy. A missing policy retains
# legacy compatibility; the caller must not reuse a legacy ROOT as a result for a
# shared-policy plan. BEDROCK (on | off) selects the native route separately: it defaults
# to on under the shared policy (the published route), and BEDROCK=off is a lawful thinner
# picture (Greg, 2026-10-07: an absent native layer never blocks the day; the reader lists
# it). This flag does not dispatch execution.
case "${SHARED_MARKET_POLICY:-}" in
  '') BEDROCK="${BEDROCK:-off}" ;;   # an older saved legacy plan only (kept as saved); every NEW run carries the policy
  FRANKIE_SHARED_MARKET_TIMELINE_V1) BEDROCK="${BEDROCK:-on}"; set -- "$@" --shared-market-policy "$SHARED_MARKET_POLICY" ;;
  *) echo 'unknown SHARED_MARKET_POLICY; retained evidence unchanged' >&2; exit 2;;
esac
case "$BEDROCK" in on|off) set -- "$@" --bedrock "$BEDROCK" ;; *) echo 'BEDROCK must be on or off' >&2; exit 2;; esac
[ -z "${FROZEN_SURVIVORS:-}" ] || set -- "$@" --frozen-survivors "$FROZEN_SURVIVORS"
case "${RESUME:-off}" in on) set -- "$@" --resume;; off) ;; *) echo 'RESUME must be on or off' >&2; exit 2;; esac
# FRANKIE_ROOT_NATIVE_OVERLAP (on | off, default on): with the native pass on, ROOT process 2 (native traversal) runs in a
# forked child beside process 1 (legacy pass) inside this held lane; off keeps the serial order. Outputs are the same files
# by the same calls either way; work/native-overlap.json records the child, its CPUs, seconds and outcome.
case "${FRANKIE_ROOT_NATIVE_OVERLAP:-on}" in on|off) export FRANKIE_ROOT_NATIVE_OVERLAP="${FRANKIE_ROOT_NATIVE_OVERLAP:-on}";;
  *) echo 'FRANKIE_ROOT_NATIVE_OVERLAP must be on or off' >&2; exit 2;; esac
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_experiment_root.py" "$@"
