# Existing day-loop child only; it cannot allocate a lane or launch a provider.
set -eu
: "${MARKETS_SHA:?staged commit required}"; : "${CODE_ROOT:?staged checkout required}"
: "${SUCCESSOR_OPERATION:?owner request required}"; : "${SUCCESSOR_PHASE:?phase required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || exit 2
case "$SUCCESSOR_OPERATION" in /opt/frankie-box/work/experiment/*/successors/*/requests/*.json) ;; *) exit 2;; esac
case "$SUCCESSOR_OPERATION" in *..*) exit 2;; esac
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_successor_dispatch.py" \
  --operation "$SUCCESSOR_OPERATION" --phase "$SUCCESSOR_PHASE"
