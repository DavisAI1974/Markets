# The CPU watchdog (frankie_box_cpu_watch.py; Greg, session 8: "if we forget a place it just kicks in after a couple of
# minutes"). ACTION=once (default): ONE read-only pass now (every Frankie process's affinity against its booking, every
# running step's lane against the resolver's plan), the record under /opt/frankie-box/work/cpu-watch/<stamp>.json and one
# line in watch.log. ACTION=loop: a pass every INTERVAL (120) seconds, DETACHED (systemd-run unit frankie-cpu-watch, else
# setsid), bounded by MAX_SECONDS (43200); ACTION=status: the last lines of watch.log and the newest record; ACTION=stop:
# stop the detached loop (its own unit; it never touches a Frankie job). Its own flock: two watchers never run a pass at
# once; its own workflow group (box-cpu-watch-<instance>) beside the box-progress probes.
# Corrections are ON by default (Greg, session 8: off only when set to off), each a FRANKIE_* run setting on the record; the
# queue's kick starts ACTION=loop itself (idempotent), so the loop runs without anyone remembering:
#   FRANKIE_CPU_WATCH_CORRECT=on  re-pin (affinity only): a thread outside its booking back inside it, a step root
#                                 narrower than its lane widened to it. Cannot grow a pool sized at start (said on the record).
#   FRANKIE_CPU_WATCH_RESIZE=on   the lawful stop-and-resume of a step whose planned lane is >= 1.5x its running lane and
#                                 which names a resume mechanism (ROOT: the day-bound save marker + grow + resume + kick;
#                                 the digest render: FRANKIE_DIGEST_STOP_FILE at a pass boundary + the same command again);
#                                 chosen by WALL-CLOCK only (the estimate on the record), never by cost; never a kill.
# SSM runs this under sh: POSIX only. Needs CODE_ROOT (a staged checkout) or MARKETS_SHA.
set -eu
ROOT=/opt/frankie-box; ACTION="${ACTION:-once}"; MARKETS_SHA="${MARKETS_SHA:-}"; CODE_ROOT="${CODE_ROOT:-}"
WATCH="$ROOT/work/cpu-watch"; UNIT=frankie-cpu-watch
case "$ACTION" in once|loop|status|stop) ;; *) echo "ACTION must be once, loop, status or stop" >&2; exit 2;; esac
case "${INTERVAL:-120}" in ""|*[!0-9]*) echo "INTERVAL must be whole seconds" >&2; exit 2;; esac
case "${MAX_SECONDS:-43200}" in ""|*[!0-9]*) echo "MAX_SECONDS must be whole seconds" >&2; exit 2;; esac
case "${FRANKIE_CPU_WATCH_CORRECT:-on}" in on|off) ;; *) echo "FRANKIE_CPU_WATCH_CORRECT must be on or off" >&2; exit 2;; esac
case "${FRANKIE_CPU_WATCH_RESIZE:-on}" in on|off) ;; *) echo "FRANKIE_CPU_WATCH_RESIZE must be on or off" >&2; exit 2;; esac
case "$CODE_ROOT" in *..*) echo "no .. in CODE_ROOT" >&2; exit 2;; esac
case "$CODE_ROOT" in "") ;; "$ROOT"/code/*/markets) ;; *) echo "CODE_ROOT must be $ROOT/code/<...>/markets" >&2; exit 2;; esac
if [ "$ACTION" = status ]; then
  echo "### $WATCH"; [ -f "$WATCH/watch.log" ] && tail -n "${LINES:-20}" "$WATCH/watch.log" || echo "no watch.log yet"
  NEWEST=$(ls -1 "$WATCH"/*.json 2>/dev/null | grep -v '/resize-' | tail -n 1 || true)
  [ -n "$NEWEST" ] && { echo "### newest record $NEWEST"; cat "$NEWEST"; }
  ls -1 "$WATCH"/resize-*.json 2>/dev/null | while read -r R; do echo "### resize request $R"; cat "$R"; done
  if command -v systemctl >/dev/null 2>&1; then systemctl is-active "$UNIT" 2>/dev/null | sed "s/^/### loop unit $UNIT: /" || true; fi
  exit 0
fi
if [ "$ACTION" = stop ]; then
  if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet "$UNIT" 2>/dev/null; then systemctl stop "$UNIT"; echo "### $UNIT stopped"; else echo "### no $UNIT loop running"; fi
  exit 0
fi
if [ -z "$CODE_ROOT" ] && [ -n "$MARKETS_SHA" ]; then
  for C in "$ROOT"/code/"$MARKETS_SHA"-*/markets; do if [ -f "$C/deploy/aws/box/frankie_box_cpu_watch.py" ]; then CODE_ROOT="$C"; fi; done
fi
[ -n "$CODE_ROOT" ] || { echo "no checkout of ${MARKETS_SHA:-?} with frankie_box_cpu_watch.py on the box: pass CODE_ROOT=<a staged checkout carrying it> or stage this commit first" >&2; exit 2; }
TOOL="$CODE_ROOT/deploy/aws/box/frankie_box_cpu_watch.py"
[ -f "$TOOL" ] || { echo "$TOOL is not there (that checkout predates the watchdog)" >&2; exit 2; }
PY="$ROOT/venv/bin/python"; [ -x "$PY" ] || PY=python3
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 FRANKIE_CPU_WATCH_CORRECT="${FRANKIE_CPU_WATCH_CORRECT:-on}" FRANKIE_CPU_WATCH_RESIZE="${FRANKIE_CPU_WATCH_RESIZE:-on}"
mkdir -p "$WATCH"
echo "### cpu watch $ACTION: code $TOOL ($(git -C "$CODE_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)), correct=$FRANKIE_CPU_WATCH_CORRECT resize=$FRANKIE_CPU_WATCH_RESIZE"
case "$ACTION" in
  once) exec "$PY" -I -S -B "$TOOL" --work-dir "$WATCH" --window "${WINDOW:-1}" ;;
  loop)
    if command -v systemd-run >/dev/null 2>&1; then
      if systemctl is-active --quiet "$UNIT" 2>/dev/null; then echo "### $UNIT already runs; nothing started"; exit 0; fi
      systemd-run --unit "$UNIT" --collect -p "StandardOutput=append:$WATCH/loop.log" -p "StandardError=append:$WATCH/loop.log" \
        -E PYTHONDONTWRITEBYTECODE=1 -E PYTHONNOUSERSITE=1 -E "FRANKIE_CPU_WATCH_CORRECT=$FRANKIE_CPU_WATCH_CORRECT" -E "FRANKIE_CPU_WATCH_RESIZE=$FRANKIE_CPU_WATCH_RESIZE" \
        "$PY" -I -S -B "$TOOL" --loop --interval "${INTERVAL:-120}" --max-seconds "${MAX_SECONDS:-43200}" --work-dir "$WATCH" --window "${WINDOW:-1}"
      echo "### $UNIT started (every ${INTERVAL:-120} s for ${MAX_SECONDS:-43200} s); ACTION=status reads it, ACTION=stop ends it"
    else
      setsid "$PY" -I -S -B "$TOOL" --loop --interval "${INTERVAL:-120}" --max-seconds "${MAX_SECONDS:-43200}" --work-dir "$WATCH" --window "${WINDOW:-1}" >> "$WATCH/loop.log" 2>&1 < /dev/null &
      echo "### watch loop started detached (pid $!, no systemd-run here)"
    fi ;;
esac
