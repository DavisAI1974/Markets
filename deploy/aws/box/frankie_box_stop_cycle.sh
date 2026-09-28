# Greg, 2026-09-28 ("the run is too expensive, stop immediately"): stop the running cycle launch on the box. Cancelling
# the GitHub run does not stop its SSM command, so this ends run_actual_sunday_ec2.py and its whole process group (the
# classroom / reading workers with it): TERM, then KILL after 10 s. Receipted; deletes nothing; resumes from receipts.
set -u
ROOT=/opt/frankie-box
mkdir -p "$ROOT/receipts"
pids=$(pgrep -f 'run_actual_sunday_ec2\.py' || true)
if [ -z "$pids" ]; then echo "no cycle launch running"; exit 0; fi
echo "### running cycle launch processes"
ps -o pid,pgid,etime,pcpu,rss,cmd -p "$(echo $pids | tr ' ' ',')" | cut -c1-220
groups=$(for p in $pids; do ps -o pgid= -p "$p" | tr -d ' '; done | sort -u)
# /bin/kill: SSM runs this under dash, whose builtin kill refuses `-- -<pgid>` (run 36406841877)
for g in $groups; do /bin/kill -s TERM -- "-$g" && echo "TERM group $g"; done
for p in $pids; do /bin/kill -s TERM "$p" 2>/dev/null && echo "TERM $p"; done
sleep 10
left=$(pgrep -f 'run_actual_sunday_ec2\.py' || true)
if [ -n "$left" ]; then
  for g in $groups; do /bin/kill -s KILL -- "-$g" && echo "KILL group $g"; done
  for p in $left; do /bin/kill -s KILL "$p" 2>/dev/null && echo "KILL $p"; done
fi
sleep 2
after=$(pgrep -f 'run_actual_sunday_ec2\.py' || true)
printf '{"schema":"FRANKIE_BOX_CYCLE_STOP_RECEIPT_V1","at":%s,"pids":"%s","groups":"%s","remaining":"%s","reason":"%s"}\n' \
  "$(date +%s)" "$(echo $pids)" "$(echo $groups)" "$(echo $after)" "${REASON:-operator stop}" | tee "$ROOT/receipts/cycle-stop-$(date +%s).json"
[ -z "$after" ] && echo "STOPPED" || { echo "STILL RUNNING: $after"; exit 2; }
