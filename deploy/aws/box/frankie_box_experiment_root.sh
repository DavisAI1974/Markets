# The experiment's ROOT for any ingested day (frankie_box_experiment_root.py): the day's sealed ingest read in place, the
# same whole-day pin, Session.derive with bedrock OFF (ROOT process 1 always; process 4, the digest, only with DIGEST=on
# for a classroom-arm day). No authorship, no re-ingest, no model call. Inputs: CODE_ROOT, INGESTION_RECEIPT (the day's
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
# New shared-input requests explicitly select the required native policy. A
# missing policy retains legacy compatibility; the caller must not reuse a legacy
# ROOT as a result for a shared-policy plan. This flag does not dispatch execution.
case "${SHARED_MARKET_POLICY:-}" in
  '') ;;
  FRANKIE_SHARED_MARKET_TIMELINE_V1) set -- "$@" --bedrock on --shared-market-policy "$SHARED_MARKET_POLICY" ;;
  *) echo 'unknown SHARED_MARKET_POLICY; retained evidence unchanged' >&2; exit 2;;
esac
[ -z "${FROZEN_SURVIVORS:-}" ] || set -- "$@" --frozen-survivors "$FROZEN_SURVIVORS"
case "${RESUME:-off}" in on) set -- "$@" --resume;; off) ;; *) echo 'RESUME must be on or off' >&2; exit 2;; esac
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_experiment_root.py" "$@"
