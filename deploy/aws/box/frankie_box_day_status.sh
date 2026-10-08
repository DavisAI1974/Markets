#!/bin/sh
# READ-ONLY one-screen status of one queue day (session 9, IMPROVEMENTS item 17; Greg: one probe instead of ad-hoc
# scripts). Nothing here writes, signals, books or starts anything; it reads the queue line, the CPU ledger, /proc, the
# day's attempt directory, the logs and the disk counters.
#
#   RUN=e2e-20231018-a2 DAY=20231018 sh deploy/aws/box/frankie_box_day_status.sh
#   (ATTEMPT=<attempt name> overrides the owner's attempt; PY=<python> overrides the venv python)
#
# Prints: the ROOT-line entry (seq, state, reason, owner attempt/cpus/booking, save_request), the ledger booking (cpus,
# live/retained, grown), the running experiment ROOT child (pid, etime, %cpu, --output-root/--resume/--data-workers/
# --digest, affinity) with its helper count and states, a running digest render, receipt / digest present, the digest
# scratch checkpoints, the last 5 lines of the day's ROOT log, the last cpu-watch line, nvme0n1's read rate over 3 s,
# and df of / and the archive.
set -u
: "${RUN:?RUN required}"
: "${DAY:?DAY required}"
BOX=/opt/frankie-box
PY=${PY:-$BOX/venv/bin/python}
[ -x "$PY" ] || PY=python3
QUEUE=$BOX/work/frankie-queue
LEDGER=$BOX/cpu-bookings
echo "=== day status $RUN $DAY at $(date -u +%Y-%m-%dT%H:%M:%SZ) on $(hostname)"

# ---- ROOT-line entry + owner + booking (one python read of the queue file and the ledger record)
OUT=$("$PY" -I -S -B - "$QUEUE/root.json" "$LEDGER" "$RUN" "$DAY" <<'EOF'
import json, os, sys
queue, ledger, run, day = sys.argv[1:5]
try:
    doc = json.load(open(queue))
except (OSError, ValueError) as error:
    print('ROOT line: unreadable %s (%s)' % (queue, error)); print('ATTEMPT='); print('BOOKING='); sys.exit(0)
e = next((x for x in doc.get('entries') or [] if x.get('run') == run and x.get('day') == day), None)
if e is None:
    print('ROOT line: no entry for %s %s' % (run, day)); print('ATTEMPT='); print('BOOKING='); sys.exit(0)
o = e.get('owner') or {}
sr = e.get('save_request') or {}
print('ROOT line: seq %s state %s' % (e.get('seq'), e.get('state')))
print('  reason: %s' % str(e.get('reason'))[:200])
print('  owner: attempt %s cpus %s booking %s commit %s' % (o.get('attempt'), o.get('cpus'), o.get('booking'),
                                                             str(o.get('commit'))[:12]))
print('  save_request: %s' % (('by %s at %s' % (sr.get('by'), sr.get('requested_utc'))) if sr else 'none'))
b = None
if o.get('booking'):
    for where in ('', 'released'):
        path = os.path.join(ledger, where, o['booking'] + '.json')
        if os.path.isfile(path):
            b = json.load(open(path)); b['_where'] = where or 'ledger'; break
if b is None:
    print('booking: %s' % ('none recorded' if not o.get('booking') else 'not in the ledger'))
else:
    pids = b.get('pids') or []
    alive = [p['pid'] for p in pids if os.path.isdir('/proc/%d' % p.get('pid', 0))]
    print('booking: %s (%s) cpus %s size %s; %s; retained %s; grown %s' % (
        b.get('booking'), b['_where'], b.get('cpu_list'), len(b.get('cpus') or []),
        'live pids %s' % alive if alive else 'no live pid',
        'yes (%s)' % (b['retained'].get('attempt') or b['retained'].get('day')) if b.get('retained') else 'no',
        len(b.get('grown') or []) or 'no'))
print('ATTEMPT=%s' % (o.get('attempt') or ''))
print('BOOKING=%s' % (o.get('booking') or ''))
EOF
)
printf '%s\n' "$OUT" | grep -v '^ATTEMPT=\|^BOOKING='
OWNER_ATTEMPT=$(printf '%s\n' "$OUT" | sed -n 's/^ATTEMPT=//p')
BOOKING=$(printf '%s\n' "$OUT" | sed -n 's/^BOOKING=//p')
ATTEMPT=${ATTEMPT:-$OWNER_ATTEMPT}
R=$BOX/work/experiment-roots/$ATTEMPT
[ -n "$ATTEMPT" ] || R=
echo "attempt dir: ${R:-unknown}"

# ---- the running experiment ROOT child (and its helpers)
echo "--- ROOT child"
FOUND=
for pid in $(pgrep -f 'frankie_box_experiment_root.py' 2>/dev/null); do
  cmd=$(tr '\0' ' ' < /proc/$pid/cmdline 2>/dev/null) || continue
  case "$cmd" in *python*frankie_box_experiment_root.py*) ;; *) continue;; esac
  [ -n "$ATTEMPT" ] && case "$cmd" in *"$ATTEMPT"*) ;; *) continue;; esac
  FOUND=1
  flags=$(printf '%s' "$cmd" | awk '{for (i = 1; i <= NF; i++) { if ($i == "--resume") printf "--resume "; else if ($i ~ /^--(output-root|data-workers|digest)$/) { printf "%s %s ", $i, $(i + 1); i++ } }}')
  echo "pid $pid $(ps -o etime=,pcpu= -p $pid | awk '{print "etime " $1 " cpu% " $2}') affinity $(taskset -cp $pid 2>/dev/null | sed 's/.*: //')"
  echo "  flags: $flags"
  kids=$(ps -o pid=,stat= --ppid $pid 2>/dev/null)
  n=$(printf '%s\n' "$kids" | grep -c '[0-9]')
  states=$(printf '%s\n' "$kids" | awk 'NF{s[substr($2,1,1)]++} END{for (k in s) printf "%s:%d ", k, s[k]}')
  echo "  helpers: $n (states $states)"
done
[ -n "$FOUND" ] || echo "none running"
RENDER=$(pgrep -f 'frankie_box_render_digest.py' 2>/dev/null | head -1)
if [ -n "$RENDER" ]; then
  echo "digest render: pid $RENDER $(ps -o etime=,pcpu= -p $RENDER | awk '{print "etime " $1 " cpu% " $2}') helpers $(ps --ppid $RENDER -o pid= 2>/dev/null | grep -c .) booking $(tr '\0' '\n' < /proc/$RENDER/environ 2>/dev/null | sed -n 's/^FRANKIE_RENDER_BOOKING=//p') lane $(tr '\0' '\n' < /proc/$RENDER/environ 2>/dev/null | sed -n 's/^FRANKIE_LANE_CPUS=//p')"
else
  echo "digest render: none running"
fi

# ---- receipt, digest, scratch checkpoints
echo "--- outputs"
if [ -n "$R" ]; then
  f=$R/calculations-receipt.json; [ -f "$f" ] && echo "receipt: present $(stat -c '%s B %y' "$f")" || echo "receipt: absent"
  f=$R/work/derivation-digest-full.md; [ -f "$f" ] && echo "digest: present $(stat -c '%s B %y' "$f")" || echo "digest: absent"
  f=$R/work/digest-render.json; [ -f "$f" ] && echo "render record: $f"
  for d in "$R"/work/derived/.digest-*; do
    [ -d "$d" ] || continue
    saves=$(ls "$d" 2>/dev/null | grep -c 'table-[0-9]*\.save\.json$')
    echo "scratch $(basename "$d"): $saves table saves $(ls "$d" | grep 'save.json$' | tr '\n' ' ')"
    for p in "$d"/table-*/passes.pkl "$d"/table-*.parallel/passes.pkl; do
      [ -f "$p" ] || continue
      echo "  $(basename "$(dirname "$p")")/passes.pkl $(stat -c '%s B %y' "$p")"
    done
    for a in "$d"/*/adopted.json; do
      [ -f "$a" ] && echo "  adopted ($(basename "$(dirname "$a")")): $(tail -1 "$a" | cut -c1-200)"
    done
  done
fi

# ---- logs
echo "--- ROOT log (last 5)"
LOG=$BOX/work/experiment/$RUN/logs/$DAY-root.log
[ -f "$LOG" ] || LOG=$(ls -t "$BOX/work/experiment/$RUN/logs/"*root*.log 2>/dev/null | head -1)
if [ -n "${LOG:-}" ] && [ -f "$LOG" ]; then echo "($LOG)"; tail -5 "$LOG" | cut -c1-220; else echo "no ROOT log under $BOX/work/experiment/$RUN/logs"; fi
echo "--- cpu-watch (last loop line)"
if [ -f "$BOX/work/cpu-watch/watch.log" ]; then tail -1 "$BOX/work/cpu-watch/watch.log" | cut -c1-220; else echo "no watch.log"; fi

# ---- disk
echo "--- disk"
DEV=${DEV:-nvme0n1}
if [ -r /sys/block/$DEV/stat ]; then
  a=$(awk '{print $3}' /sys/block/$DEV/stat); sleep 3; b=$(awk '{print $3}' /sys/block/$DEV/stat)
  echo "$DEV read: $(( (b - a) * 512 / 3 / 1048576 )) MiB/s over 3 s"
else
  echo "$DEV: no /sys/block stat"
fi
df -h / "${FRANKIE_ARCHIVE_ROOT:-$BOX/archive}" 2>/dev/null
