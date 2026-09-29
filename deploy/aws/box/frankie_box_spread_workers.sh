# Spread the ingest/verify/conform reader workers over idle CPUs (Greg, 2026-09-29: "Is there any way we can speed this
# part up?"). The conformance reader pins each worker to ONE CPU taken from cpus[1:] of the process's affinity
# (frankie_journal_reader.worker_budget), so every verify or conform started with the box's full affinity lands on the
# same CPUs 1..N: on 2026-09-29 16:50Z fourteen workers of three drains shared CPUs 1-6 at 100% while CPUs 7-31 were idle.
# This moves each single-CPU-pinned worker of every running ingest_block_sources.py process onto its own CPU, one worker
# per CPU, never CPU 0 (the reader reserves it for the ordered consumer and host), keeping any worker that already has a
# CPU to itself. It changes CPU affinity only (taskset -p): nothing is stopped, restarted, read or written, so the drains'
# results are unchanged. Prints each worker's CPU before and after. Idempotent. SSM runs this under sh: POSIX only.
# THE CPU LEDGER (Greg, 2026-09-29: "We don't double book cores or workers"; frankie_box_cores.py): a worker only ever
# moves to a CPU its OWN job may use, read from the ledger beside this script (`allowed --pid <its parent>`): a booked job's
# workers stay inside its booking (never its parent CPU, the booking's lowest); a job not in the ledger (started before
# the ledger) never moves onto a CPU a booking holds. A worker off its allowed CPUs moves back onto a free one of them. When
# the ledger cannot be read for a job, that job's workers are not moved at all.
set -u
PY=/opt/frankie-box/venv/bin/python; [ -x "$PY" ] || PY=python3
CORES="$(dirname "$0")/frankie_box_cores.py"
allowed_of() {   # $1 = a parent pid: comma list of the CPUs its workers may use; "?" when the ledger cannot say
  if [ -f "$CORES" ]; then "$PY" -I -S -B "$CORES" allowed --pid "$1" 2>/dev/null || echo "?"; else echo "?"; fi
}
PIDS=""
for P in $(pgrep -f ingest_block_sources.py); do
  A=""
  for W in $(pgrep -P "$P"); do
    L=$(taskset -pc "$W" 2>/dev/null | sed 's/.*: //')
    case "$L" in *[,-]*|"") continue;; esac                       # single-CPU pinned workers only
    [ -n "$A" ] || A=$(allowed_of "$P"); [ -n "$A" ] || A="none"
    PIDS="$PIDS $W:$L:$P:$A"
  done
done
[ -n "$PIDS" ] || { echo "no single-CPU pinned reader workers running"; exit 0; }
# a worker keeps its CPU when that CPU is one its job may use and no other worker holds it; the rest move
USED=" "; MOVE=""
for E in $PIDS; do
  R=${E#*:}; C=${R%%:*}; A=${R##*:}
  case "$USED" in *" $C "*) MOVE="$MOVE $E"; continue;; esac
  USED="$USED$C "                                                  # occupied now, whether it stays or moves
  case "$A" in "?") continue;; esac                                # ledger unreadable: never moved
  case ",$A," in *",$C,"*) ;; *) MOVE="$MOVE $E";; esac            # off the CPUs its job may use: moves back onto one
done
[ -n "$MOVE" ] || { echo "every pinned worker already has a CPU to itself inside what its job may use"; exit 0; }
for E in $MOVE; do
  W=${E%%:*}; R=${E#*:}; C=${R%%:*}; R=${R#*:}; P=${R%%:*}; A=${R#*:}
  case "$A" in "?") echo "worker $W (parent $P): its job's CPU booking could not be read; not moved (stays on CPU $C)"; continue;; esac
  N=""
  for T in $(echo "$A" | tr ',' ' '); do
    case "$T" in none) continue;; esac
    case "$USED" in *" $T "*) ;; *) N=$T; break;; esac
  done
  [ -n "$N" ] || { echo "no free CPU its job may use for worker $W (parent $P, may use ${A}; stays on CPU $C)"; continue; }
  if taskset -pc "$N" "$W" >/dev/null 2>&1; then echo "worker $W (parent $P): CPU $C -> $N"; USED="$USED$N "; else echo "worker $W: move failed (stays on CPU $C)"; fi
done
echo "pinned workers now:"; for E in $PIDS; do W=${E%%:*}; echo "  $W $(taskset -pc "$W" 2>/dev/null | sed 's/.*: //')"; done
