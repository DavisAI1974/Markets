# Re-point a ROOT-line day to a named EXISTING attempt on a RETAINED booking of SIZE CPUs (frankie_box_queue_repoint.py;
# session 9: "restart from exactly the same spot"). Inputs: CODE_ROOT (staged checkout), MARKETS_SHA (its HEAD), RUN, DAY,
# ATTEMPT (<RUN>-<DAY>-a<N>, an unfinished directory under /opt/frankie-box/work/experiment-roots with work/derive.json),
# SIZE (16|32|64), REASON, BY. Then ACTION=resume and ACTION=kick (or handover) of frankie_box_frankie_queue.sh.
set -eu
export HOME="${HOME:-/root}"
# 2026-10-09 (Greg: the code version is recorded, never compared): CODE_ROOT defaults to the NEWEST staged checkout on
# the box (frankie_box_cpu_watch.newest_staged_checkout's rule: staging-receipt.json status 'staged' for the directory's
# own commit, newest by the receipt's mtime) and MARKETS_SHA to that checkout's HEAD
if [ -z "${CODE_ROOT:-}" ]; then
  CODE_ROOT=$(/opt/frankie-box/venv/bin/python -I -S -B -c '
import json, os, re
best, parent = None, "/opt/frankie-box/code"
for name in (os.listdir(parent) if os.path.isdir(parent) else []):
    d = os.path.join(parent, name)
    m = re.fullmatch(r"([0-9a-f]{40})-[A-Za-z0-9_-]{1,96}", name)
    r, c = os.path.join(d, "staging-receipt.json"), os.path.join(d, "markets")
    if not m or os.path.islink(d) or not os.path.isfile(r):
        continue
    try:
        v = json.load(open(r))
    except ValueError:
        continue
    if v.get("status") == "staged" and v.get("commit") == m.group(1) and v.get("code_root") == c and os.path.isdir(c):
        t = os.stat(r).st_mtime
        if best is None or t > best[0]:
            best = (t, c)
print(best[1] if best else "")') || CODE_ROOT=''
  [ -n "$CODE_ROOT" ] || { echo "no CODE_ROOT given and no staged checkout under /opt/frankie-box/code" >&2; exit 2; }
  echo "### CODE_ROOT not given: the newest staged checkout $CODE_ROOT" >&2
fi
MARKETS_SHA="${MARKETS_SHA:-$(git -C "$CODE_ROOT" rev-parse HEAD 2>/dev/null || true)}"
: "${RUN:?}"; : "${DAY:?}"; : "${ATTEMPT:?}"; : "${SIZE:?}"; : "${REASON:?}"; : "${BY:?}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
case "$CODE_ROOT" in *..*) echo "no .. in CODE_ROOT" >&2; exit 2;; esac
case "$RUN$ATTEMPT" in *[!A-Za-z0-9_-]*) echo "RUN/ATTEMPT: letters, digits, _ and - only" >&2; exit 2;; esac
case "$DAY" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) echo "DAY must be YYYYMMDD" >&2; exit 2;; esac
HEAD_SHA=$(git -C "$CODE_ROOT" rev-parse HEAD 2>/dev/null) || HEAD_SHA="${MARKETS_SHA:-}"  # 2026-10-09: recorded, never compared
[ "$HEAD_SHA" = "${MARKETS_SHA:-}" ] || { echo "code version: MARKETS_SHA ${MARKETS_SHA:-unset}, checkout $CODE_ROOT at $HEAD_SHA; this step runs on (and records) $HEAD_SHA" >&2; MARKETS_SHA=$HEAD_SHA; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_queue_repoint.py" --run "$RUN" --day "$DAY" \
  --attempt "$ATTEMPT" --size "$SIZE" --reason "$REASON" --by "$BY" --code-root "$CODE_ROOT" --commit "$MARKETS_SHA"
