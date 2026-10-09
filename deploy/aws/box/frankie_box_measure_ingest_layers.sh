# Measure every ingest reduction stacked layer by layer (L0-L4), read-only, through frankie_box_run.yml.
# Writes only a fresh root under /opt/frankie-box/work/ingest-stack-measure/. Code staged at MARKETS_SHA.
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"
: "${OUTPUT_ROOT:?fresh measurement root required}"
: "${CODE_ROOT:?staged clean checkout required}"
SEGMENTS="${SEGMENTS:-24}"; ENTRIES="${ENTRIES:-20480}"
case "$MARKETS_SHA" in *[!0-9a-f]*) echo "invalid MARKETS_SHA" >&2; exit 2;; esac
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
case "$CODE_ROOT/" in *"/../"*|*"/./"*|*"//"*) echo "normalized code checkout required" >&2; exit 2;; esac
case "$SEGMENTS$ENTRIES" in *[!0-9]*|'') echo "SEGMENTS and ENTRIES must be integers" >&2; exit 2;; esac
PYTHON=/opt/frankie-box/venv/bin/python
TOOL="$CODE_ROOT/deploy/aws/box/frankie_box_measure_ingest_layers.py"
[ -x "$PYTHON" ] && [ -f "$TOOL" ] || { echo "reviewed measurement code or interpreter absent" >&2; exit 2; }
HEAD_SHA=$(git -C "$CODE_ROOT" rev-parse HEAD 2>/dev/null) || HEAD_SHA="${MARKETS_SHA:-}"  # 2026-10-09: recorded, never compared
[ "$HEAD_SHA" = "${MARKETS_SHA:-}" ] || { echo "code version: MARKETS_SHA ${MARKETS_SHA:-unset}, checkout $CODE_ROOT at $HEAD_SHA; this step runs on (and records) $HEAD_SHA" >&2; MARKETS_SHA=$HEAD_SHA; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
exec "$PYTHON" -B "$TOOL" --output-root "$OUTPUT_ROOT" --segments "$SEGMENTS" --entries "$ENTRIES"
