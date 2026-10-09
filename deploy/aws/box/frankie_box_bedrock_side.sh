# Build a running ROOT's bedrock tables beside it on idle cores (frankie_box_bedrock_side.py). Reads ROOT's finished
# sources.sqlite read-only; writes only work/derived/.digest-side-<RUN_ID>/ under the calculation root.
# Inputs: DIRECTORY (Monday calculation root), DIGEST (.digest-<hex> ROOT scratch), CPUS (comma-separated physical
# CPUs), SIBLINGS=1 to add their hyperthread siblings, CODE_ROOT (this staged checkout).
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"
: "${CODE_ROOT:?staged clean checkout required}"
: "${DIRECTORY:?Monday calculation root required}"
: "${DIGEST:?ROOT digest scratch name required}"
: "${CPUS:?comma-separated physical CPUs required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
case "$DIRECTORY" in /opt/frankie-box/work/monday-calculations/*) ;; *) echo "Monday calculation root required" >&2; exit 2;; esac
case "$DIGEST" in .digest-*) ;; *) echo "DIGEST must be a .digest-* name" >&2; exit 2;; esac
case "$CPUS" in *[!0-9,]*) echo "CPUS must be comma-separated integers" >&2; exit 2;; esac
HEAD_SHA=$(git -C "$CODE_ROOT" rev-parse HEAD 2>/dev/null) || HEAD_SHA="${MARKETS_SHA:-}"  # 2026-10-09: recorded, never compared
[ "$HEAD_SHA" = "${MARKETS_SHA:-}" ] || { echo "code version: MARKETS_SHA ${MARKETS_SHA:-unset}, checkout $CODE_ROOT at $HEAD_SHA; this step runs on (and records) $HEAD_SHA" >&2; MARKETS_SHA=$HEAD_SHA; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
set --
[ "${SIBLINGS:-0}" = 1 ] && set -- --with-siblings
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_bedrock_side.py" \
  --directory "$DIRECTORY" --digest "$DIGEST" --cpus "$CPUS" --run-id "$(date -u +%Y%m%dT%H%M%SZ)" "$@"
