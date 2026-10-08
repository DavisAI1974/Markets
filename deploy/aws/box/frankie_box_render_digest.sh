# Render-only (Greg, 2026-09-28; experiment roots 2026-10-08): re-write a retained Monday calculation root's (or experiment root's) digest in the current digest schema
# from the saved layers; the calculations are not re-run (frankie_box_render_digest.py). Box CPUs only, no Pod, no model.
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"
: "${CODE_ROOT:?staged checkout required}"
: "${OUTPUT_ROOT:?retained Monday calculation root required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "inactive staged checkout required" >&2; exit 2;; esac
case "$OUTPUT_ROOT" in /opt/frankie-box/work/monday-calculations/*|/opt/frankie-box/work/experiment-roots/*) ;; *) echo "retained Monday calculation root or experiment root required" >&2; exit 2;; esac
[ -s "$OUTPUT_ROOT/calculations-receipt.json" ] || { echo "no retained calculations receipt under $OUTPUT_ROOT" >&2; exit 3; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
# The retained layers carry the same snapshots ROOT reads; pin the serializer as ROOT does.
if ! /opt/frankie-box/venv/bin/python -B -c 'import cloudpickle; assert cloudpickle.__version__ == "3.1.2"'; then
  /opt/frankie-box/venv/bin/python -m pip install --no-cache-dir cloudpickle==3.1.2
fi
# Session 6 (2026-10-08): the render runs on the CPUs it is given, never inside a live booking. Session 8: the CPU set
# comes from the ONE resolver (frankie_box_cores.py plan --step digest-render): every CPU outside the live/retained
# bookings, whole physical cores first; FRANKIE_LANE_CPUS, when set, must lie inside that free set (refused with the
# bookings named, exit 4); unset is NO LONGER the process's own affinity (that overlapped a retained booking on the
# 64-vCPU box). The render is pinned there (taskset) and the digest writer sizes its helpers from it
# (frankie_box_digest_document.lane_cpus). The plan JSON (CPUs, reasoning, the physical cores shared with bookings) is
# printed and kept at $OUTPUT_ROOT/work/render-cpu-plan.json.
PLAN=$(CODE_ROOT="$CODE_ROOT" /opt/frankie-box/venv/bin/python -I -S -B "$CODE_ROOT/deploy/aws/box/frankie_box_cores.py" plan --step digest-render) || { echo "refused: $PLAN" >&2; exit 4; }
echo "### render CPU plan: $PLAN"
mkdir -p "$OUTPUT_ROOT/work" && printf '%s\n' "$PLAN" > "$OUTPUT_ROOT/work/render-cpu-plan.json"
LANE=$(printf '%s' "$PLAN" | /opt/frankie-box/venv/bin/python -I -S -B -c 'import json,sys; print(json.load(sys.stdin)["cpu_list"])')
[ -n "$LANE" ] || { echo "refused: the CPU plan named no CPUs" >&2; exit 4; }
export FRANKIE_LANE_CPUS="$LANE"
# Session 8: the render's LAWFUL stop point. A file at FRANKIE_DIGEST_STOP_FILE (default below; the CPU watchdog's resize
# writes it, an operator may too) stops the render at its next PASS BOUNDARY with exit 75 after the per-pass checkpoint
# (frankie_box_digest_parallel.stop_requested); the same command again resumes at the first unsaved pass. A stale stop file
# from an earlier stop is removed here before the start so a resume never stops itself.
export FRANKIE_DIGEST_STOP_FILE="${FRANKIE_DIGEST_STOP_FILE:-$OUTPUT_ROOT/work/render-stop-request.json}"
rm -f "$FRANKIE_DIGEST_STOP_FILE"
echo "### render stop file (a lawful stop at the next pass boundary): $FRANKIE_DIGEST_STOP_FILE"
exec taskset -c "$FRANKIE_LANE_CPUS" /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_render_digest.py" \
  --commit "$MARKETS_SHA" --output-root "$OUTPUT_ROOT"
