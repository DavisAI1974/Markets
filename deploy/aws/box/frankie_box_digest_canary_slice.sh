# Digest decode-ladder canary on a 2 GiB slice of a frames spool (ROOT-digest role, 2026-10-08; Greg: measure a slice,
# extrapolate; "we only do 1 pass"). Old writer (FRANKIE_DIGEST_DECODES=5) vs new (=2) on the SAME slice, sha256 of both
# tables, the fused context against cross_context, both inverse proofs: frankie_box_digest_canary_slice.py. Read-only on
# the spool; writes under /opt/frankie-box/work/digest-canary-slice/<stamp>/ (tables deleted at the end, report kept).
# DRY RUN by default: RUN=1 executes. Inputs: CODE_ROOT (an inactive staged checkout: the pinned producers for the c15
# codec), SPOOL (default: a2's frames spool), FRANKIE_LANE_CPUS (required with RUN=1; e.g. 16-31), BYTES (default 2 GiB),
# SETTINGS (default 5,2), KEEP=1 keeps the tables. The lane is refused (exit 4) when any of its CPUs sits inside a live
# or retained booking under /opt/frankie-box/cpu-bookings; the canary is then pinned to the lane (taskset).
set -eu
: "${CODE_ROOT:?staged checkout required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "inactive staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
export SPOOL="${SPOOL:-/opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1/work/derived/.rows/frames.jsonl}"
[ -s "$SPOOL" ] || { echo "SPOOL is not a non-empty file: $SPOOL" >&2; exit 3; }
export BYTES="${BYTES:-2147483648}" SETTINGS="${SETTINGS:-5,2}"
case "$BYTES" in ''|*[!0-9]*) echo "BYTES must be a positive integer" >&2; exit 2;; esac
export PYTHONPATH="$CODE_ROOT" PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
ARGS="--spool $SPOOL --bytes $BYTES --settings $SETTINGS"
[ -n "${FRANKIE_DIGEST_DISK_RESERVE:-}" ] && ARGS="$ARGS --reserve $FRANKIE_DIGEST_DISK_RESERVE"
[ "${RUN:-0}" = "1" ] && ARGS="$ARGS --run"
[ "${KEEP:-0}" = "1" ] && ARGS="$ARGS --keep"
if [ "${RUN:-0}" = "1" ]; then
  : "${FRANKIE_LANE_CPUS:?FRANKIE_LANE_CPUS (e.g. 16-31) required to run}"
  # the booking guard first (a dry run of the same script on the same lane; exit 4 names the booking), then the run pinned
  FRANKIE_LANE_CPUS="$FRANKIE_LANE_CPUS" /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_digest_canary_slice.py" \
    --spool "$SPOOL" --bytes "$BYTES" --settings "$SETTINGS" >/dev/null
  export FRANKIE_LANE_CPUS
  # shellcheck disable=SC2086
  exec taskset -c "$FRANKIE_LANE_CPUS" nice -n 5 /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_digest_canary_slice.py" $ARGS
fi
# shellcheck disable=SC2086
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_digest_canary_slice.py" $ARGS
