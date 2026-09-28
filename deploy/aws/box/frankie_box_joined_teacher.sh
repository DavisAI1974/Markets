# The joined teacher data (research/kalshi/frankie_boss/SPEC-joined-teachers.md): the Monday layer files read in place,
# joined per F_LAST group, the per-cell couplings with their circular-shift null, and the teacher sources. No model
# call; no layer is written. Resumable: a rerun with the same OUTPUT_ROOT skips every saved part, series and block.
# Inputs: OUTPUT_ROOT (under /opt/frankie-box/work/joined-teacher/), CALCULATIONS_RECEIPT + CALCULATIONS_SHA256 (the
# completed Monday calculations), CODE_ROOT (this staged checkout), optional WORKERS, LAGS, ALL_PAIRS=1.
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"
: "${OUTPUT_ROOT:?joined-teacher output root required}"
: "${CODE_ROOT:?staged clean checkout required}"
: "${CALCULATIONS_RECEIPT:?completed Monday receipt required}"
: "${CALCULATIONS_SHA256:?independent completed receipt SHA256 required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
case "$OUTPUT_ROOT" in /opt/frankie-box/work/joined-teacher/*) ;; *) echo "output under /opt/frankie-box/work/joined-teacher/ required" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
set -- --out "$OUTPUT_ROOT" --calculations-receipt "$CALCULATIONS_RECEIPT" --calculations-sha256 "$CALCULATIONS_SHA256"
[ -n "${WORKERS:-}" ] && set -- "$@" --workers "$WORKERS"
[ -n "${LAGS:-}" ] && set -- "$@" --lags "$LAGS"
[ "${ALL_PAIRS:-0}" = 1 ] && set -- "$@" --all-pairs
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_joined_teacher.py" "$@"
