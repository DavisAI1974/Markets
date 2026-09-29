# Export an existing root's calculations for the experiments (Greg, 2026-09-29): the derive stage's JSON layer files
# and derive.json, hard-linked (no rewrite, no extra disk) under /opt/frankie-box/work/experiment-calcs/<DAY>/cycle-<CYCLE>/
# with a MANIFEST (bytes, sha256). Bedrock layers are not exported. Read-only on the root; no model call.
# Inputs: WORK (the root's work directory, e.g. /opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48/work),
# DAY (trading day, e.g. 20211004), CYCLE (e.g. 00), CODE_ROOT (the staged checkout).
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"
: "${CODE_ROOT:?staged clean checkout required}"
: "${WORK:?root work directory required}"
: "${DAY:?trading day required}"
: "${CYCLE:?cycle required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
case "$WORK" in /opt/frankie-box/work/*) ;; *) echo "work directory under /opt/frankie-box/work required" >&2; exit 2;; esac
case "$DAY$CYCLE" in *[!0-9]*) echo "DAY and CYCLE must be digits" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
exec /opt/frankie-box/venv/bin/python -B - "$CODE_ROOT/deploy/aws/box" "$WORK" "$DAY" "$CYCLE" <<'PY'
import json, sys
sys.path.insert(0, sys.argv[1])
import frankie_box_brain as B
m = B.export_calculations(sys.argv[2], sys.argv[3], sys.argv[4])
print(json.dumps(dict(files=[(f['name'], f['bytes'], f['sha256']) for f in m['files']], not_exported=m['not_exported']), indent=1))
PY
