# Job 0 step 4 (the session): start Frankie's cycle session on his box as a detached transient service, with the
# heartbeat beside it. The session is Claude Code (installed per COACH_AGENT_SETUP_S93) reading the task document
# (research/kalshi/frankie_boss/operations/ROOT_CYCLE_00_TASK_20260920.md, box edition) from this branch's checkout
# on the box; the calculations are Frankie's, run against the restored rows with the staged producers.
# Backend, in order: /etc/markets/frankie-box.env if Greg placed one (chmod 600; ANTHROPIC_API_KEY or Bedrock vars);
# else SSM SecureString /markets/frankie/anthropic-api-key (us-east-2) read into the service environment only;
# else Bedrock through the instance role (CLAUDE_CODE_USE_BEDROCK=1, us-east-1). A backend that cannot answer a
# one-line preflight refuses the start and says so. Inputs: DAY (20211003), CYCLE (00), MARKETS_REF (this branch),
# ACTION (start | status | preflight; default status). Never stops a running session (that is Greg's word).
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
backend_env() {
  # prints NAME=VALUE lines for the service environment (to a 600 file the service reads; removed when it ends)
  if [ -s /etc/markets/frankie-box.env ]; then cat /etc/markets/frankie-box.env; echo "FRANKIE_BACKEND=env-file"; return; fi
  key=$("$ROOT/venv/bin/python" -c "import boto3;print(boto3.client('ssm',region_name='us-east-2').get_parameter(Name='/markets/frankie/anthropic-api-key',WithDecryption=True)['Parameter']['Value'])" 2>/dev/null) && { echo "ANTHROPIC_API_KEY=$key"; echo "FRANKIE_BACKEND=anthropic-api-ssm"; return; }
  echo "CLAUDE_CODE_USE_BEDROCK=1"; echo "AWS_REGION=us-east-1"; echo "AWS_DEFAULT_REGION=us-east-1"; echo "ANTHROPIC_MODEL=us.anthropic.claude-opus-4-6-v1:0"; echo "ANTHROPIC_SMALL_FAST_MODEL=us.anthropic.claude-haiku-4-5-20251001-v1:0"; echo "FRANKIE_BACKEND=bedrock-role"
}
preflight() {
  ENVF="$S/backend.env"; umask 077; backend_env > "$ENVF"; chmod 600 "$ENVF"
  echo "backend: $(grep '^FRANKIE_BACKEND=' "$ENVF" | cut -d= -f2)"
  ( set -a; . "$ENVF"; set +a; cd "$S" && timeout 180 claude -p "Reply with exactly: FRANKIE-BOX-ONLINE" --output-format text 2>&1 | tail -3 ) | tee "$ROOT/logs/preflight-$CYCLE.log"
  grep -q "FRANKIE-BOX-ONLINE" "$ROOT/logs/preflight-$CYCLE.log" && { echo "preflight: OK"; return 0; }
  echo "preflight: FAILED (no backend answered; see logs/preflight-$CYCLE.log)"; return 1
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
for n in ('/markets/frankie/github-token','/markets/frankie/anthropic-api-key'):
    try: s.get_parameter(Name=n,WithDecryption=True); print(n, 'readable (not printed)')
    except Exception as e: print(n, code(e))"
  for t in claude node systemd-run; do printf '%-12s %s\n' "$t" "$(command -v "$t" || echo absent)"; done
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
    PROMPT="You are Frankie, the principal session for cycle $CYCLE of the 20211003 run, running on your own box. Read and follow, in full, the task document at $TASK (box edition). Everything you need is under $ROOT (request/, data/, producers/, markets/, venv/); write your four files to $S/out/. Keep $S/phase and $S/note current as the document says. When the four files pass the checks in the document, write the word done to $S/done and stop."
    systemctl reset-failed "$UNIT.service" 2>/dev/null
    systemd-run --unit "$UNIT" --collect -p WorkingDirectory="$S" -p EnvironmentFile="$S/backend.env" -p Environment="HOME=/root" -p Environment="PATH=$ROOT/venv/bin:/usr/local/bin:/usr/bin:/bin" \
      -p StandardOutput=append:"$ROOT/logs/session-$CYCLE.log" -p StandardError=append:"$ROOT/logs/session-$CYCLE.log" \
      /usr/bin/claude -p "$PROMPT" --output-format text --dangerously-skip-permissions --add-dir "$ROOT" || { echo "session service start failed"; exit 4; }
    sleep 5; printf '{"schema":"FRANKIE_BOX_SESSION_START_RECEIPT_V1","at":%s,"unit":"%s","cycle":"%s","markets_ref":"%s","markets_head":"%s","request_sha256":"%s","backend":"%s"}\n' "$(date +%s)" "$UNIT" "$CYCLE" "$MARKETS_REF" "$(git -C "$ROOT/markets" rev-parse HEAD)" "$(cat "$S/request_sha256")" "$(grep '^FRANKIE_BACKEND=' "$S/backend.env" | cut -d= -f2)" > "$ROOT/receipts/session-start-$CYCLE-$(date +%s).json"
    status ;;
  *) echo "ACTION must be start, status, preflight or verify"; exit 2 ;;
esac
