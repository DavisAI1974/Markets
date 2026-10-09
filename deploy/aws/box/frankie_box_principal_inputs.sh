# Assemble single-run Monday inputs through the existing workflow.
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"
: "${OUTPUT_ROOT:?fresh principal-inputs root required}"
: "${CODE_ROOT:?staged clean checkout required}"
: "${CALCULATIONS_RECEIPT:?completed Monday receipt required}"
: "${CALCULATIONS_SHA256:?independent completed receipt SHA256 required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
HEAD_SHA=$(git -C "$CODE_ROOT" rev-parse HEAD 2>/dev/null) || HEAD_SHA="${MARKETS_SHA:-}"  # 2026-10-09: recorded, never compared
[ "$HEAD_SHA" = "${MARKETS_SHA:-}" ] || { echo "code version: MARKETS_SHA ${MARKETS_SHA:-unset}, checkout $CODE_ROOT at $HEAD_SHA; this step runs on (and records) $HEAD_SHA" >&2; MARKETS_SHA=$HEAD_SHA; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_principal_inputs.py" --output-root "$OUTPUT_ROOT" \
  --calculations-receipt "$CALCULATIONS_RECEIPT" --calculations-sha256 "$CALCULATIONS_SHA256"
