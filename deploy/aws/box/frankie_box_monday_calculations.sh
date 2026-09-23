# One explicit calculation stage on the sealed Monday source; no controller or ingestion.
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"
: "${CODE_ROOT:?staged checkout required}"
: "${AUTHORSHIP:?actual Monday authorship receipt required}"
: "${AUTHORSHIP_SHA256:?authorship byte hash required}"
: "${OUTPUT_ROOT:?fresh Monday calculation root required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "inactive staged checkout required" >&2; exit 2;; esac
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_monday_calculations.py" \
  --commit "$MARKETS_SHA" --authorship "$AUTHORSHIP" --authorship-sha256 "$AUTHORSHIP_SHA256" --output-root "$OUTPUT_ROOT"
