# Spread the ingest/verify/conform reader workers over idle CPUs (Greg, 2026-09-29: "Is there any way we can speed this
# part up?"). The conformance reader pins each worker to ONE CPU taken from cpus[1:] of the process's affinity
# (frankie_journal_reader.worker_budget), so every verify or conform started with the box's full affinity lands on the
# same CPUs 1..N: on 2026-09-29 16:50Z fourteen workers of three drains shared CPUs 1-6 at 100% while CPUs 7-31 were idle.
# This moves each single-CPU-pinned worker of every running ingest_block_sources.py process onto its own CPU, one worker
# per CPU, never CPU 0 (the reader reserves it for the ordered consumer and host), keeping any worker that already has a
# CPU to itself. It changes CPU affinity only (taskset -p): nothing is stopped, restarted, read or written, so the drains'
# results are unchanged. Prints each worker's CPU before and after. Idempotent. SSM runs this under sh: POSIX only.
set -u
NCPU=$(nproc)
PIDS=""
for P in $(pgrep -f ingest_block_sources.py); do
  for W in $(pgrep -P "$P"); do
    L=$(taskset -pc "$W" 2>/dev/null | sed 's/.*: //')
    case "$L" in *[,-]*|"") ;; *) PIDS="$PIDS $W:$L:$P";; esac   # single-CPU pinned workers only
  done
done
[ -n "$PIDS" ] || { echo "no single-CPU pinned reader workers running"; exit 0; }
# CPUs already held by exactly one worker stay with it; the rest move to CPUs no worker holds
USED=" "; MOVE=""
for E in $PIDS; do
  W=${E%%:*}; R=${E#*:}; C=${R%%:*}
  case "$USED" in *" $C "*) MOVE="$MOVE $E";; *) USED="$USED$C ";; esac
done
[ -n "$MOVE" ] || { echo "every pinned worker already has a CPU to itself"; exit 0; }
N=1
for E in $MOVE; do
  W=${E%%:*}; R=${E#*:}; C=${R%%:*}; P=${R#*:}
  while [ "$N" -lt "$NCPU" ]; do case "$USED" in *" $N "*) N=$((N + 1));; *) break;; esac; done
  [ "$N" -lt "$NCPU" ] || { echo "no free CPU left for worker $W (stays on CPU $C)"; continue; }
  if taskset -pc "$N" "$W" >/dev/null 2>&1; then echo "worker $W (parent $P): CPU $C -> $N"; USED="$USED$N "; else echo "worker $W: move failed (stays on CPU $C)"; fi
done
echo "pinned workers now:"; for E in $PIDS; do W=${E%%:*}; echo "  $W $(taskset -pc "$W" 2>/dev/null | sed 's/.*: //')"; done
