# Granite post-class discussion coordinator (frankie_box_granite_meeting.py): one ephemeral llama.cpp meeting on Frankie's
# view of the day's exchange, the record written beside it. Role V2 / rules V3 R17: coordination only, never evidence.
# Inputs: CODE_ROOT, MARKETS_SHA, EXCHANGE_VIEW (an exchange-frankie.json under the experiment work), OUT_DIR (under the
# owning experiment), BRAIN (optional), LLAMA_SERVER + GGUF_MODEL (the pinned binary and model; omitted = the local route
# on the canonical install paths, so the gate REFUSES VISIBLY when the runtime is not installed; INPUTS_ONLY=1 is the only
# inputs-only switch), MEETING_THREADS (optional positive integer: the caller's lane placement; the day lane's shared
# adviser CPU gives 1). The Python gate refuses to call the model while a pin in knowledge/GRANITE_MEETING_RUNTIME_V1.json
# is an explicit blank, the parameters are unconfirmed or a file differs. No Pod, no GPU, no standing service: the server
# lives for one meeting.
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"; : "${CODE_ROOT:?staged clean checkout required}"
: "${EXCHANGE_VIEW:?Frankie exchange view required}"; : "${OUT_DIR:?meeting output directory required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
case "$EXCHANGE_VIEW" in /opt/frankie-box/work/experiment/*/exchange/*/exchange-frankie.json) ;; *) echo "EXCHANGE_VIEW must be an exchange-frankie.json under the owning experiment" >&2; exit 2;; esac
case "$OUT_DIR" in /opt/frankie-box/work/experiment/*/meeting/*) ;; *) echo "OUT_DIR must be under the owning experiment's meeting directory" >&2; exit 2;; esac
for v in "$EXCHANGE_VIEW" "$OUT_DIR" "${BRAIN:-}" "${LLAMA_SERVER:-}" "${GGUF_MODEL:-}"; do
  case "$v" in *..*) echo "no .. in paths" >&2; exit 2;; esac
done
set -- --exchange "$EXCHANGE_VIEW" --out-dir "$OUT_DIR"
if [ -n "${BRAIN:-}" ]; then
  case "$BRAIN" in /opt/frankie-box/*) ;; *) echo "BRAIN must be under /opt/frankie-box" >&2; exit 2;; esac
  set -- "$@" --brain "$BRAIN"
fi
if [ "${INPUTS_ONLY:-0}" = "1" ]; then
  set -- "$@" --inputs-only
elif [ -n "${LLAMA_SERVER:-}" ] && [ -n "${GGUF_MODEL:-}" ]; then
  case "$LLAMA_SERVER" in /opt/frankie-box/granite/*) ;; *) echo "LLAMA_SERVER must be under /opt/frankie-box/granite" >&2; exit 2;; esac
  case "$GGUF_MODEL" in /opt/frankie-box/granite/*.gguf) ;; *) echo "GGUF_MODEL must be a .gguf under /opt/frankie-box/granite" >&2; exit 2;; esac
  set -- "$@" --route local --binary "$LLAMA_SERVER" --model "$GGUF_MODEL"
else
  # unset: the local route on the canonical install paths; the meeting's gate refuses visibly (a refused record), never
  # a silent inputs-only
  set -- "$@" --route local
fi
if [ -n "${MEETING_THREADS:-}" ]; then
  case "$MEETING_THREADS" in ""|*[!0-9]*|0) echo "MEETING_THREADS must be a positive integer" >&2; exit 2;; esac
  set -- "$@" --threads "$MEETING_THREADS"
fi
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
exec nice -n 10 /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_granite_meeting.py" "$@"
