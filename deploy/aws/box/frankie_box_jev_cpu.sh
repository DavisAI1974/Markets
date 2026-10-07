# Jev runs sequentially inside the original held day slot; no provisioning or new booking.
set -eu
: "${MARKETS_SHA:?retained dispatched source required}"; : "${CODE_ROOT:?retained staged source required}"
: "${JEV_REQUEST:?exact owner-bound JEV_CPU_REQUEST_V1 path required}"
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo 'retained Jev checkout differs' >&2; exit 2; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_jev_cpu.py" --request "$JEV_REQUEST"
