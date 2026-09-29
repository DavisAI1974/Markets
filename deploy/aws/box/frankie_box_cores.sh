# The per-box CPU booking ledger (frankie_box_cores.py; Greg, 2026-09-29: "Correct 16 and no double booking"; "We don't
# double book cores or workers"). The dispatchable side: ACTION=show (default, READ-ONLY: every CPU -> the booking or the
# unbooked Frankie process that holds it, its live use, the free count, whether a day run (16) or an ingest (8) can book
# now; JSON=1 adds the raw record; WINDOW = seconds between the two /proc samples, default 2), ACTION=reap (releases every
# booking whose pids are all gone, each with a receipt under /opt/frankie-box/cpu-bookings/released/), ACTION=release
# BOOKING=<id> (one booking, by hand, on Greg's word). Booking itself is done by the jobs (frankie_box_ingest_block.sh,
# frankie_box_experiment.py), never by a dispatch. The ledger code comes from CODE_ROOT (a staged checkout
# /opt/frankie-box/code/<...>/markets or an ingest worktree /opt/frankie-box/ingest-code/<sha>) or, without it, from the
# dispatched commit's ingest worktree or staged checkout on the box; nothing is checked out here. Nothing is stopped,
# signalled or re-pinned. SSM runs this under sh: POSIX only.
set -eu
ROOT=/opt/frankie-box; ACTION="${ACTION:-show}"; MARKETS_SHA="${MARKETS_SHA:-}"; CODE_ROOT="${CODE_ROOT:-}"
case "$ACTION" in show|reap|release) ;; *) echo "ACTION must be show, reap or release (jobs book for themselves)" >&2; exit 2;; esac
case "${WINDOW:-2}" in ""|*[!0-9]*) echo "WINDOW must be whole seconds" >&2; exit 2;; esac
case "$CODE_ROOT" in *..*) echo "no .. in CODE_ROOT" >&2; exit 2;; esac
case "$CODE_ROOT" in "") ;; "$ROOT"/code/*/markets|"$ROOT"/ingest-code/*) ;; *) echo "CODE_ROOT must be $ROOT/code/<...>/markets or $ROOT/ingest-code/<sha>" >&2; exit 2;; esac
if [ -z "$CODE_ROOT" ] && [ -n "$MARKETS_SHA" ]; then
  if [ -f "$ROOT/ingest-code/$MARKETS_SHA/deploy/aws/box/frankie_box_cores.py" ]; then CODE_ROOT="$ROOT/ingest-code/$MARKETS_SHA"
  else
    for C in "$ROOT"/code/"$MARKETS_SHA"-*/markets; do if [ -f "$C/deploy/aws/box/frankie_box_cores.py" ]; then CODE_ROOT="$C"; fi; done
  fi
fi
[ -n "$CODE_ROOT" ] || { echo "no checkout of $MARKETS_SHA with frankie_box_cores.py on the box: pass CODE_ROOT=<a staged checkout carrying it> or stage this commit first (frankie_box_stage_code.sh ACTION=stage)" >&2; exit 2; }
TOOL="$CODE_ROOT/deploy/aws/box/frankie_box_cores.py"
[ -f "$TOOL" ] || { echo "$TOOL is not there (that checkout predates the ledger)" >&2; exit 2; }
echo "### ledger code $TOOL ($(git -C "$CODE_ROOT" rev-parse HEAD 2>/dev/null || echo unknown))"
PY="$ROOT/venv/bin/python"; [ -x "$PY" ] || PY=python3
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
case "$ACTION" in
  show) if [ "${JSON:-0}" = 1 ]; then exec "$PY" -I -S -B "$TOOL" show --window "${WINDOW:-2}" --json; fi
        exec "$PY" -I -S -B "$TOOL" show --window "${WINDOW:-2}" ;;
  reap) exec "$PY" -I -S -B "$TOOL" reap ;;
  release) : "${BOOKING:?BOOKING=<booking id> required}"
           exec "$PY" -I -S -B "$TOOL" release --booking "$BOOKING" --reason "released by dispatch ${MARKETS_SHA:-?}" ;;
esac
