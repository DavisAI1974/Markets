# Explicit data preparation/publication only, through frankie_box_run.yml.
# The workflow supplies MARKETS_SHA last. Code must already be staged at that
# exact commit; this launcher never fetches, checks out, starts or stops anything.
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"
: "${ACTION:?prepare or publish action required}"
: "${OUTPUT_ROOT:?fresh preparation root required}"
CODE_ROOT="${CODE_ROOT:-/opt/frankie-box/markets}"
case "$MARKETS_SHA" in *[!0-9a-f]*) echo "invalid MARKETS_SHA" >&2; exit 2;; esac
[ "${#MARKETS_SHA}" -eq 40 ] || { echo "full MARKETS_SHA required" >&2; exit 2; }
case "$CODE_ROOT" in /opt/frankie-box/*) ;; *) echo "code checkout must be under the box root" >&2; exit 2;; esac
case "$CODE_ROOT/" in *"/../"*|*"/./"*|*"//"*) echo "normalized code checkout required" >&2; exit 2;; esac
PYTHON=/opt/frankie-box/venv/bin/python
ADAPTER="$CODE_ROOT/deploy/aws/box/frankie_box_prepare_trading_day.py"
[ -x "$PYTHON" ] && [ -f "$ADAPTER" ] || { echo "reviewed preparation code or interpreter absent" >&2; exit 2; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
PYTHONPATH="$CODE_ROOT"
export PYTHONPATH
case "$ACTION" in
  prepare)
    : "${CONFIGURATION:?pinned configuration path required}"
    : "${CONFIGURATION_SHA256:?configuration byte hash required}"
    exec "$PYTHON" -B "$ADAPTER" prepare --configuration "$CONFIGURATION" \
      --configuration-sha256 "$CONFIGURATION_SHA256" --commit "$MARKETS_SHA" --output-root "$OUTPUT_ROOT"
    ;;
  publish)
    : "${UPLOAD_MAP:?private upload map required}"
    : "${UPLOAD_MAP_SHA256:?upload map byte hash required}"
    exec "$PYTHON" -B "$ADAPTER" publish --commit "$MARKETS_SHA" --output-root "$OUTPUT_ROOT" \
      --upload-map "$UPLOAD_MAP" --upload-map-sha256 "$UPLOAD_MAP_SHA256"
    ;;
  *) echo "ACTION must be prepare or publish" >&2; exit 2;;
esac
