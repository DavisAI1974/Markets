# Re-point a ROOT-line day to a named EXISTING attempt on a RETAINED booking of SIZE CPUs (frankie_box_queue_repoint.py;
# session 9: "restart from exactly the same spot"). Inputs: CODE_ROOT (staged checkout), MARKETS_SHA (its HEAD), RUN, DAY,
# ATTEMPT (<RUN>-<DAY>-a<N>, an unfinished directory under /opt/frankie-box/work/experiment-roots with work/derive.json),
# SIZE (16|32|64), REASON, BY. Then ACTION=resume and ACTION=kick (or handover) of frankie_box_frankie_queue.sh.
set -eu
export HOME="${HOME:-/root}"
: "${CODE_ROOT:?staged checkout required}"; : "${MARKETS_SHA:?full dispatched commit required}"
: "${RUN:?}"; : "${DAY:?}"; : "${ATTEMPT:?}"; : "${SIZE:?}"; : "${REASON:?}"; : "${BY:?}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
case "$CODE_ROOT" in *..*) echo "no .. in CODE_ROOT" >&2; exit 2;; esac
case "$RUN$ATTEMPT" in *[!A-Za-z0-9_-]*) echo "RUN/ATTEMPT: letters, digits, _ and - only" >&2; exit 2;; esac
case "$DAY" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) echo "DAY must be YYYYMMDD" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_queue_repoint.py" --run "$RUN" --day "$DAY" \
  --attempt "$ATTEMPT" --size "$SIZE" --reason "$REASON" --by "$BY" --code-root "$CODE_ROOT" --commit "$MARKETS_SHA"
