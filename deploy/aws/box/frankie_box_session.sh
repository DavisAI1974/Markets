# Job 0 step 4 (the session): start Frankie's cycle session on his box as a detached transient service, with the
# heartbeat beside it. THE ENGINE IS THE BOSS (Greg, 2026-09-21: no keys, no external model, that is why the
# BOSS exists). The session reads the task document (research/kalshi/frankie_boss/operations/
# ROOT_CYCLE_00_TASK_20260920.md, box edition) from this branch's checkout on the box; the calculations are
# Frankie's, run against the restored rows with the staged producers. The engine is the BOSS: frankie_box_boss_session.py
# (the retained Granite vLLM on the RunPod Pod over jobs_v1); `preflight` proves the reach and starts nothing.
# Inputs: DAY (20211003), CYCLE (00), MARKETS_REF (this branch), ACTION (start | status | preflight | verify;
# default status). Never stops a running session (that is Greg's word).
set -u
ROOT=/opt/frankie-box; S="$ROOT/session"
DAY="${DAY:-20211003}"; CYCLE="${CYCLE:-00}"; MARKETS_REF="${MARKETS_REF:-claude/cycle-0-frankie-box-rerun-od5sxk}"; ACTION="${ACTION:-status}"
UNIT="frankie-cycle-$CYCLE"
export HOME=/root
mkdir -p "$S/out" "$ROOT/receipts" "$ROOT/logs"
status() {
  echo "### session status"; systemctl is-active "$UNIT.service" 2>/dev/null || echo "(no $UNIT service)"
  echo "phase: $(cat "$S/phase" 2>/dev/null || echo '-')  note: $(head -c 200 "$S/note" 2>/dev/null || echo '-')"
  echo "done: $([ -e "$S/done" ] && echo yes || echo no)"; ls -la "$S/out" 2>/dev/null
  echo "--- session log tail"; tail -n 25 "$ROOT/logs/session-$CYCLE.log" 2>/dev/null
  echo "--- heartbeat log tail"; tail -n 5 "$ROOT/logs/heartbeat-$CYCLE.log" 2>/dev/null
  systemctl is-active "frankie-heartbeat-$CYCLE.service" 2>/dev/null || echo "(no heartbeat service)"
}
preflight() {
  # The engine is the BOSS: the retained Granite vLLM on Pod g7y3g2w1kor4l3 over jobs_v1 (frankie_box_boss_session.py).
  # Verifies the request against the authored source contract, computes the timing labels by code, reads the Pod
  # record through the SecureString /markets/frankie/granite-service (never printed) and probes /health. Starts nothing.
  echo "engine: BOSS (retained Granite vLLM, jobs_v1; frankie_box_boss_session.py --stage preflight)"
  "$ROOT/venv/bin/python" "$ROOT/markets/deploy/aws/box/frankie_box_boss_session.py" --session "$S" --day "$DAY" --cycle "$CYCLE" --stage preflight
}
verify() {
  echo "### verify (no session started): request digest through the adapter, the task document, the pusher's token reach"
  git -C "$ROOT/markets" fetch -q --depth 1 origin "$MARKETS_REF" && git -C "$ROOT/markets" checkout -q FETCH_HEAD && echo "markets HEAD $(git -C "$ROOT/markets" rev-parse HEAD)"
  TASK="$ROOT/markets/research/kalshi/frankie_boss/operations/ROOT_CYCLE_00_TASK_20260920.md"; [ -s "$TASK" ] && echo "task document: $(wc -c < "$TASK") bytes, sha256 $(sha256sum "$TASK" | cut -c1-16)" || echo "task document MISSING"
  "$ROOT/venv/bin/python" -c "
import json,sys,time; sys.path.insert(0,'$ROOT/markets')
t=time.time()
from research.kalshi.frankie_boss.frankie_principal_adapter import digest
req=json.loads(open('$ROOT/request/session-request.json','rb').read())
print('request_sha256', digest(req)); print('request_id', req.get('request_id')); print('instruction chars', len(req.get('instruction','')))
print('adapter import + digest %.1fs' % (time.time()-t))" || echo "adapter digest FAILED"
  "$ROOT/venv/bin/python" -c "
import boto3
def code(e): return getattr(e,'response',{}).get('Error',{}).get('Code') or type(e).__name__
s=boto3.client('ssm',region_name='us-east-2')
for n in ('/markets/frankie/github-token',):
    try: s.get_parameter(Name=n,WithDecryption=True); print(n, 'readable (not printed)')
    except Exception as e: print(n, code(e))"
  for t in git systemd-run; do printf '%-12s %s\n' "$t" "$(command -v "$t" || echo absent)"; done
  echo "phase file: $(cat "$S/phase" 2>/dev/null || echo '-')"
}
case "$ACTION" in
  status) status ;;
  preflight) preflight ;;
  verify) verify ;;
  start)
    if systemctl is-active --quiet "$UNIT.service"; then echo "$UNIT is already running; not restarting (Greg's word)"; status; exit 0; fi
    [ -s "$ROOT/request/session-request.json" ] || { echo "request not on the box"; exit 2; }
    [ -x "$ROOT/venv/bin/python" ] || { echo "venv not staged"; exit 2; }
    git -C "$ROOT/markets" fetch -q --depth 1 origin "$MARKETS_REF" && git -C "$ROOT/markets" checkout -q FETCH_HEAD
    TASK="$ROOT/markets/research/kalshi/frankie_boss/operations/ROOT_CYCLE_00_TASK_20260920.md"; [ -s "$TASK" ] || { echo "task document missing at $TASK"; exit 2; }
    preflight || exit 3
    "$ROOT/venv/bin/python" -c "
import json,sys; sys.path.insert(0,'$ROOT/markets')
from research.kalshi.frankie_boss.frankie_principal_adapter import digest
print(digest(json.loads(open('$ROOT/request/session-request.json','rb').read())))" > "$S/request_sha256" || { echo "request digest failed"; exit 2; }
    echo "request_sha256 $(cat "$S/request_sha256")"
    echo "verified" > "$S/phase"; echo "request and data plane verified on the box; session starting" > "$S/note"; rm -f "$S/done"
    systemctl reset-failed "frankie-heartbeat-$CYCLE.service" 2>/dev/null
    systemd-run --unit "frankie-heartbeat-$CYCLE" --collect -p WorkingDirectory="$S" -p StandardOutput=append:"$ROOT/logs/heartbeat-$CYCLE.log" -p StandardError=append:"$ROOT/logs/heartbeat-$CYCLE.log" \
      "$ROOT/venv/bin/python" "$ROOT/markets/deploy/aws/box/frankie_box_heartbeat.py" --session "$S" --day "$DAY" --cycle "$CYCLE" --base "$MARKETS_REF" >/dev/null 2>&1 || echo "heartbeat service start failed"
    systemctl reset-failed "$UNIT.service" 2>/dev/null
    systemd-run --unit "$UNIT" --collect -p WorkingDirectory="$S" -p StandardOutput=append:"$ROOT/logs/session-$CYCLE.log" -p StandardError=append:"$ROOT/logs/session-$CYCLE.log" \
      "$ROOT/venv/bin/python" "$ROOT/markets/deploy/aws/box/frankie_box_boss_session.py" --session "$S" --day "$DAY" --cycle "$CYCLE" --stage run >/dev/null 2>&1 \
      && echo "$UNIT started (the BOSS session; hours; watch the heartbeat and the session log)" || { echo "$UNIT start failed"; exit 3; }
    sleep 5
    status ;;
  *) echo "ACTION must be start, status, preflight or verify"; exit 2 ;;
esac
