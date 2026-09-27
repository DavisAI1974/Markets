# One explicit calculation stage on the sealed Monday source; no controller or ingestion.
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"
: "${CODE_ROOT:?staged checkout required}"
: "${AUTHORSHIP:?actual Monday authorship receipt required}"
: "${AUTHORSHIP_SHA256:?authorship byte hash required}"
: "${OUTPUT_ROOT:?Monday calculation root required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "inactive staged checkout required" >&2; exit 2;; esac
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
# Full-state snapshots include local calculator factories; pin the serializer.
if ! /opt/frankie-box/venv/bin/python -B -c 'import cloudpickle; assert cloudpickle.__version__ == "3.1.2"'; then
  /opt/frankie-box/venv/bin/python -m pip install --no-cache-dir cloudpickle==3.1.2
fi
args=()
if [ -n "${RESUME_CHECKPOINT:-}" ]; then
  : "${BINDING_SHA256:?original calculation source-binding hash required}"
  args+=(--resume-checkpoint "$RESUME_CHECKPOINT" --binding-sha256 "$BINDING_SHA256")
fi
case "${RECONSTRUCT_MISSING:-0}" in
  0) ;;
  1) [ -n "${RESUME_CHECKPOINT:-}" ] || exit 2; args+=(--reconstruct-missing) ;;
  *) echo "RECONSTRUCT_MISSING must be 0 or 1" >&2; exit 2 ;;
esac
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_monday_calculations.py" \
  --commit "$MARKETS_SHA" --authorship "$AUTHORSHIP" --authorship-sha256 "$AUTHORSHIP_SHA256" --output-root "$OUTPUT_ROOT" \
  --data-workers "${DATA_WORKERS:-1}" "${args[@]}"
