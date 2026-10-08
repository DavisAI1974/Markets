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
# Session 6 (2026-10-08): the render runs on the CPUs it is given, never inside a live booking. FRANKIE_LANE_CPUS (e.g.
# 16-31) is checked against /opt/frankie-box/cpu-bookings (frankie_box_cores.live_bookings: a booking with a live pid, or
# a retained one, holds its CPUs); any overlap refuses (exit 4) and names the booking; the render is then pinned there
# (taskset) and the digest writer sizes its helpers from it (frankie_box_digest_document.lane_cpus). Unset = the
# process's own affinity, as before.
if [ -n "${FRANKIE_LANE_CPUS:-}" ]; then
  CODE_ROOT="$CODE_ROOT" FRANKIE_LANE_CPUS="$FRANKIE_LANE_CPUS" /opt/frankie-box/venv/bin/python -B - <<'PY' || exit 4
import os, sys
sys.path.insert(0, os.environ['CODE_ROOT'] + '/deploy/aws/box')
import frankie_box_cores as C
wanted = set()
for part in os.environ['FRANKIE_LANE_CPUS'].split(','):
    part = part.strip()
    if part:
        low, _, high = part.partition('-')
        wanted.update(range(int(low), int(high or low) + 1))
held = [(b.get('booking'), sorted(set(b.get('cpus') or []) & wanted)) for b in C.live_bookings()
        if (b.get('_alive') or b.get('_retained')) and set(b.get('cpus') or []) & wanted]
if held:
    print('refused: FRANKIE_LANE_CPUS %s overlaps a live or retained booking: %s' % (
        os.environ['FRANKIE_LANE_CPUS'], '; '.join('%s holds %s' % (b, c) for b, c in held)), file=sys.stderr)
    sys.exit(4)
print('lane %s free of live bookings' % os.environ['FRANKIE_LANE_CPUS'])
PY
  export FRANKIE_LANE_CPUS
  exec taskset -c "$FRANKIE_LANE_CPUS" /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_render_digest.py" \
    --commit "$MARKETS_SHA" --output-root "$OUTPUT_ROOT"
fi
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_render_digest.py" \
  --commit "$MARKETS_SHA" --output-root "$OUTPUT_ROOT"
