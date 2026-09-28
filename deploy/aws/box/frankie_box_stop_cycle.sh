# Greg, 2026-09-28 ("the run is too expensive, stop immediately"): stop the running cycle launch on the box. Cancelling
# the GitHub run does not stop its SSM command, so this ends run_actual_sunday_ec2.py and its whole process group (the
# classroom / reading workers with it): TERM, then KILL after 10 s. Receipted; deletes nothing; resumes from receipts.
# TARGET (Greg, 2026-09-28 "stop the bedrock process"): cycle (default, run_actual_sunday_ec2.py) or render
# (frankie_box_render_digest.py, the render-only digest step).
set -u
ROOT=/opt/frankie-box
case "${TARGET:-cycle}" in
  cycle) SCRIPT='run_actual_sunday_ec2\.py' ;;
  render) SCRIPT='frankie_box_render_digest\.py' ;;
  *) echo "TARGET must be cycle or render"; exit 2 ;;
esac
# only a python interpreter running the script (never a tail, grep or editor naming it); its workers go with its group
PATTERN="^[^ ]*/python[0-9.]*( -[^ ]+)* [^ ]*/$SCRIPT( |\$)"
own=$(ps -o pgid= -p $$ | tr -d ' ')
groups_of() { for p in $1; do ps -o pgid= -p "$p" | tr -d ' '; done | sort -u | awk -v own="$own" '$1 > 1 && $1 != own'; }
REASON=$(printf '%s' "${REASON:-operator stop}" | tr -c 'A-Za-z0-9 _.:,-' '_')
mkdir -p "$ROOT/receipts"
pids=$(pgrep -f "$PATTERN" || true)
if [ -z "$pids" ]; then echo "no ${TARGET:-cycle} process running"; exit 0; fi
echo "### running ${TARGET:-cycle} processes"
ps -o pid,pgid,etime,pcpu,rss,cmd -p "$(echo $pids | tr ' ' ',')" | cut -c1-220
groups=$(groups_of "$pids")
# /bin/kill: SSM runs this under dash, whose builtin kill refuses `-- -<pgid>` (run 36406841877)
for g in $groups; do /bin/kill -s TERM -- "-$g" && echo "TERM group $g"; done
for p in $pids; do /bin/kill -s TERM "$p" 2>/dev/null && echo "TERM $p"; done
sleep 10
left=$(pgrep -f "$PATTERN" || true)
if [ -n "$left" ]; then
  for g in $(groups_of "$left"); do /bin/kill -s KILL -- "-$g" && echo "KILL group $g"; done
  for p in $left; do /bin/kill -s KILL "$p" 2>/dev/null && echo "KILL $p"; done
fi
sleep 2
after=$(pgrep -f "$PATTERN" || true)
printf '{"schema":"FRANKIE_BOX_CYCLE_STOP_RECEIPT_V1","target":"%s","at":%s,"pids":"%s","groups":"%s","remaining":"%s","reason":"%s"}\n' \
  "${TARGET:-cycle}" "$(date +%s)" "$(echo $pids)" "$(echo $groups)" "$(echo $after)" "$REASON" | tee "$ROOT/receipts/${TARGET:-cycle}-stop-$(date +%s)-$$.json"
[ -z "$after" ] && echo "STOPPED" || { echo "STILL RUNNING: $after"; exit 2; }
