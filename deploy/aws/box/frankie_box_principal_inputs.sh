# Assemble single-run Monday inputs through the existing workflow.
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"
: "${OUTPUT_ROOT:?fresh principal-inputs root required}"
: "${CODE_ROOT:?staged clean checkout required}"
: "${CALCULATIONS_RECEIPT:?completed Monday receipt required}"
: "${CALCULATIONS_SHA256:?independent completed receipt SHA256 required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_principal_inputs.py" --output-root "$OUTPUT_ROOT" \
  --calculations-receipt "$CALCULATIONS_RECEIPT" --calculations-sha256 "$CALCULATIONS_SHA256"
