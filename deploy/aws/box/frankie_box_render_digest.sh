# Render-only (Greg, 2026-09-28): re-write a retained Monday calculation root's digest in the current digest schema
# from the saved layers; the calculations are not re-run (frankie_box_render_digest.py). Box CPUs only, no Pod, no model.
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"
: "${CODE_ROOT:?staged checkout required}"
: "${OUTPUT_ROOT:?retained Monday calculation root required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "inactive staged checkout required" >&2; exit 2;; esac
case "$OUTPUT_ROOT" in /opt/frankie-box/work/monday-calculations/*) ;; *) echo "retained Monday calculation root required" >&2; exit 2;; esac
[ -s "$OUTPUT_ROOT/calculations-receipt.json" ] || { echo "no retained calculations receipt under $OUTPUT_ROOT" >&2; exit 3; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
# The retained layers carry the same snapshots ROOT reads; pin the serializer as ROOT does.
if ! /opt/frankie-box/venv/bin/python -B -c 'import cloudpickle; assert cloudpickle.__version__ == "3.1.2"'; then
  /opt/frankie-box/venv/bin/python -m pip install --no-cache-dir cloudpickle==3.1.2
fi
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_render_digest.py" \
  --commit "$MARKETS_SHA" --output-root "$OUTPUT_ROOT"
