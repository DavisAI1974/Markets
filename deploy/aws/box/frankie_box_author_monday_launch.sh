# Author the Monday 20211004 cycle-0 launch inputs (Frankie principal), through frankie_box_run.yml.
# Read-only against the sealed container and recovery; writes one fresh root under
# /opt/frankie-box/work/monday-launch/. Code must already be staged at MARKETS_SHA (set last by the workflow).
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"
: "${OUTPUT_ROOT:?fresh authorship root required}"
: "${PREPARATION_ROOT:?fresh preparation root the configuration will name}"
: "${CODE_ROOT:?staged clean checkout required}"
case "$MARKETS_SHA" in *[!0-9a-f]*) echo "invalid MARKETS_SHA" >&2; exit 2;; esac
[ "${#MARKETS_SHA}" -eq 40 ] || { echo "full MARKETS_SHA required" >&2; exit 2; }
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
case "$CODE_ROOT/" in *"/../"*|*"/./"*|*"//"*) echo "normalized code checkout required" >&2; exit 2;; esac
PYTHON=/opt/frankie-box/venv/bin/python
AUTHOR="$CODE_ROOT/deploy/aws/box/frankie_box_author_monday_launch.py"
[ -x "$PYTHON" ] && [ -f "$AUTHOR" ] || { echo "reviewed authorship code or interpreter absent" >&2; exit 2; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
PYTHONPATH="$CODE_ROOT"
export PYTHONPATH
exec "$PYTHON" -B "$AUTHOR" --commit "$MARKETS_SHA" --output-root "$OUTPUT_ROOT" --preparation-root "$PREPARATION_ROOT"
