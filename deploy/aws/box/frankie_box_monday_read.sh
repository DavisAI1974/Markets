# Frankie's read of the Monday 20211004 trading day through the digest stack (whole day, no cutoff), through
# frankie_box_run.yml. Read-only against the sealed container and recovery; writes one fresh root under
# /opt/frankie-box/work/monday-read/. Code must already be staged at MARKETS_SHA (set last by the workflow).
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"
: "${OUTPUT_ROOT:?fresh read root required}"
: "${CODE_ROOT:?staged clean checkout required}"
case "$MARKETS_SHA" in *[!0-9a-f]*) echo "invalid MARKETS_SHA" >&2; exit 2;; esac
[ "${#MARKETS_SHA}" -eq 40 ] || { echo "full MARKETS_SHA required" >&2; exit 2; }
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
case "$CODE_ROOT/" in *"/../"*|*"/./"*|*"//"*) echo "normalized code checkout required" >&2; exit 2;; esac
PYTHON=/opt/frankie-box/venv/bin/python
TOOL="$CODE_ROOT/deploy/aws/box/frankie_box_monday_read.py"
[ -x "$PYTHON" ] && [ -f "$TOOL" ] || { echo "reviewed read code or interpreter absent" >&2; exit 2; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
PYTHONPATH="$CODE_ROOT"
export PYTHONPATH
exec "$PYTHON" -B "$TOOL" --commit "$MARKETS_SHA" --output-root "$OUTPUT_ROOT"
