# The experiment's classroom arm V2 for one day of a run of any length (frankie_box_experiment_classroom_v2.py; the run's
# day count is the plan's, never assumed here): the V1 arm's package, Frankie's
# Exit codes: 0 complete (receipt.json status complete); 3 refused with receipt.json status refused; 75 saved on a stop
# (phase-progress.json last_event saved; every completed operation retained); any other failure writes receipt.json status
# failed/refused with the reason before the error propagates (nothing fails silently, Greg 2026-10-07).
# code answers, the host's grade and correction, the completion and Frankie's brain entry, exactly as V1, PLUS Frankie's
# historical data points (the BOSS teacher's external section, its answers, grade, correction and completion; Jev's
# material carries it). No model, no Pod, no Granite. Inputs: CODE_ROOT (staged checkout), DAY (YYYYMMDD), CALCULATIONS
# (the day's experiment ROOT, DIGEST=on, under /opt/frankie-box/work/experiment-roots/), TEACHER_ROWS (default
# /opt/frankie-box/work/experiment-teacher-rows/<DAY>), PREVIOUS (optional: the previous classroom day's
# <root>/work/classroom), BRAIN (default /opt/frankie-box/brain), DAY_EXTERNAL + DAY_EXTERNAL_SHA256 (optional, together:
# the day file and its sha256; default: the file beside the sealed ingest the teacher rows came from, checked against its
# day-external-receipt.json).
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"; : "${CODE_ROOT:?staged clean checkout required}"
: "${DAY:?YYYYMMDD required}"; : "${CALCULATIONS:?the experiment ROOT of the day required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
case "$DAY" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) echo "DAY must be YYYYMMDD" >&2; exit 2;; esac
TEACHER_ROWS="${TEACHER_ROWS:-/opt/frankie-box/work/experiment-teacher-rows/$DAY}"; BRAIN="${BRAIN:-/opt/frankie-box/brain}"
case "$CALCULATIONS" in /opt/frankie-box/work/experiment-roots/*) ;; *) echo "CALCULATIONS under /opt/frankie-box/work/experiment-roots required" >&2; exit 2;; esac
case "$TEACHER_ROWS" in /opt/frankie-box/work/experiment-teacher-rows/*) ;; *) echo "TEACHER_ROWS under experiment-teacher-rows required" >&2; exit 2;; esac
case "${PREVIOUS:-}" in ""|/opt/frankie-box/work/experiment-roots/*/work/classroom) ;; *) echo "PREVIOUS must be an experiment root's work/classroom" >&2; exit 2;; esac
case "${DAY_EXTERNAL:-}" in ""|/opt/frankie-box/*) ;; *) echo "DAY_EXTERNAL must be under /opt/frankie-box" >&2; exit 2;; esac
if [ -n "${DAY_EXTERNAL:-}" ] || [ -n "${DAY_EXTERNAL_SHA256:-}" ]; then
  XS="${DAY_EXTERNAL_SHA256:-}"
  [ -n "${DAY_EXTERNAL:-}" ] && [ "${#XS}" = 64 ] || { echo "DAY_EXTERNAL and a 64-hex DAY_EXTERNAL_SHA256 go together" >&2; exit 2; }
fi
case "$CALCULATIONS$TEACHER_ROWS${PREVIOUS:-}$BRAIN${DAY_EXTERNAL:-}" in *..*) echo "no .. in paths" >&2; exit 2;; esac
set -- --day "$DAY" --calculations "$CALCULATIONS" --teacher-rows "$TEACHER_ROWS" --brain "$BRAIN"
[ -z "${PREVIOUS:-}" ] || set -- "$@" --previous "$PREVIOUS"
[ -z "${DAY_EXTERNAL:-}" ] || set -- "$@" --day-external "$DAY_EXTERNAL" --day-external-sha256 "$DAY_EXTERNAL_SHA256"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
# Math-library thread caps = this process's own CPU affinity count (the booked lane the Run started it under; Greg,
# 2026-10-07: BLAS/OpenMP caps to the assigned CPUs), set only when the caller did not. OpenBLAS already defaults to
# the affinity count, so the cap names the same number explicitly and keeps it from ever exceeding the lane; the
# runner records the caps in received.cpu_pinning.thread_caps.
LANE_N=$(/opt/frankie-box/venv/bin/python -c 'import os; print(len(os.sched_getaffinity(0)))') || LANE_N=""
if [ -n "$LANE_N" ]; then
  export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-$LANE_N}" OMP_NUM_THREADS="${OMP_NUM_THREADS:-$LANE_N}" \
         MKL_NUM_THREADS="${MKL_NUM_THREADS:-$LANE_N}"
fi
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_experiment_classroom_v2.py" "$@"
