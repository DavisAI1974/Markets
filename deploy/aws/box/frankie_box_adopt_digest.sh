# Adopt a STOPPED ROOT's finished sources.sqlite and legacy tables as save points (frankie_box_adopt_digest.py).
# the calculation root is unlocked; writes sources.save.json and table-NNNN.save.json receipts and nothing else.
# Inputs: DIRECTORY (the Monday calculation root), DIGEST (.digest-<hex> scratch name under work/derived),
# OLD_CODE_ROOT (the staged checkout the stopped ROOT ran), CODE_ROOT (this staged checkout).
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"
: "${CODE_ROOT:?staged clean checkout required}"
: "${DIRECTORY:?Monday calculation root required}"
: "${DIGEST:?.digest-<hex> scratch name required}"
: "${OLD_CODE_ROOT:?staged checkout the stopped ROOT ran required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
case "$OLD_CODE_ROOT" in /opt/frankie-box/code/*/markets) ;; *) echo "old staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
case "$DIRECTORY" in /opt/frankie-box/work/monday-calculations/*) ;; *) echo "Monday calculation root required" >&2; exit 2;; esac
case "$DIGEST" in .digest-*) ;; *) echo "DIGEST must be a .digest-* name" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_adopt_digest.py" \
  --directory "$DIRECTORY" --digest "$DIGEST" --old-code-root "$OLD_CODE_ROOT"
