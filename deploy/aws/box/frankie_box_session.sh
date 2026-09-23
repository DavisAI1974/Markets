# Job 0 step 4 (the session): start Frankie's cycle session on his box as a detached transient service, with the
# heartbeat beside it. THE ENGINE IS THE BOSS (Greg, 2026-09-21: no keys, no external model, that is why the
# BOSS exists). The session reads the task document (research/kalshi/frankie_boss/operations/
# ROOT_CYCLE_00_TASK_20260920.md, box edition) from this branch's checkout on the box; the calculations are
# Frankie's, run against the restored rows with the staged producers. The engine is the BOSS: frankie_box_boss_session.py
# (the retained Granite vLLM on the RunPod Pod over jobs_v1); `preflight` proves the reach and starts nothing.
# Inputs: DAY (20211003), CYCLE (00), MARKETS_SHA (full dispatched commit), ACTION (start | status | preflight | verify;
# default status; restart_session stops ONLY the session unit with a receipt to apply a session-code fix;
# fetch_correction takes the host's exported classroom-correction-request.json through MAP_URL into request/;
# correction runs the session's Dipole classroom correction turn as its own unit; derive_only = checkpoint E of the
# bedrock plan: the legacy five and the bedrock derived in the foreground and the V6 digest measured, no model call,
# the session unit untouched). Never stops a Pod, a box or the native host runner (Greg's word).
set -u
ROOT=/opt/frankie-box; S="$ROOT/session"
DAY="${DAY:-20211003}"; CYCLE="${CYCLE:-00}"; MARKETS_SHA="${MARKETS_SHA:-}"; ACTION="${ACTION:-status}"
UNIT="frankie-cycle-$CYCLE"
mkdir -p "$S/out" "$ROOT/receipts" "$ROOT/logs"
status() {
  echo "### session status"; systemctl is-active "$UNIT.service" 2>/dev/null || echo "(no $UNIT service)"
  echo "phase: $(cat "$S/phase" 2>/dev/null || echo '-')  note: $(head -c 200 "$S/note" 2>/dev/null || echo '-')"
  echo "done: $([ -e "$S/done" ] && echo yes || echo no)"; ls -la "$S/out" 2>/dev/null
  echo "--- session log tail"; tail -n 25 "$ROOT/logs/session-$CYCLE.log" 2>/dev/null
  echo "--- heartbeat log tail"; tail -n 5 "$ROOT/logs/heartbeat-$CYCLE.log" 2>/dev/null
  if [ -s "$ROOT/logs/correction-$CYCLE.log" ]; then echo "--- correction log tail ($(systemctl is-active "frankie-correction-$CYCLE.service" 2>/dev/null))"; tail -n 12 "$ROOT/logs/correction-$CYCLE.log"; fi
  systemctl is-active "frankie-heartbeat-$CYCLE.service" 2>/dev/null || echo "(no heartbeat service)"
}
checkout_markets() {
  [[ "${MARKETS_SHA:-}" =~ ^[0-9a-f]{40}$ ]] || { echo "MARKETS_SHA must be the full dispatched commit"; return 2; }
  local previous resolved running stamp intent receipt
  previous="$(git -C "$ROOT/markets" rev-parse HEAD)" || return 2
  git -C "$ROOT/markets" diff --quiet || { echo "markets has uncommitted source changes; preserved"; return 2; }
  git -C "$ROOT/markets" diff --cached --quiet || { echo "markets has staged source changes; preserved"; return 2; }
  if [ "$previous" = "$MARKETS_SHA" ]; then echo "markets HEAD $previous (already pinned)"; return 0; fi
  running="$(systemctl list-units --type=service --state=active,activating,deactivating --no-legend --plain \
    'frankie-cycle-*.service' 'frankie-heartbeat-*.service' 'frankie-correction-*.service')" \
    || { echo "could not verify session units are idle; checkout unchanged"; return 2; }
  [ -z "$running" ] || { echo "a Frankie unit is active; checkout unchanged"; return 2; }
  git -C "$ROOT/markets" fetch -q --depth 1 origin -- "$MARKETS_SHA" \
    || { echo "fetch of pinned commit failed; checkout unchanged"; return 2; }
  resolved="$(git -C "$ROOT/markets" rev-parse FETCH_HEAD)" || return 2
  [ "$resolved" = "$MARKETS_SHA" ] || { echo "fetched commit differs from the dispatch pin"; return 2; }
  stamp="$(date +%s%N)"
  intent="$ROOT/receipts/markets-checkout-intent-$stamp.json"
  receipt="$ROOT/receipts/markets-checkout-receipt-$stamp.json"
  "$ROOT/venv/bin/python" - "$intent" "$previous" "$MARKETS_SHA" <<'PY' || return 2
import json, os, pathlib, sys
path=pathlib.Path(sys.argv[1])
body=dict(schema='FRANKIE_MARKETS_CHECKOUT_INTENT_V1',from_commit=sys.argv[2],to_commit=sys.argv[3])
with path.open('x',encoding='utf-8') as stream:
    stream.write(json.dumps(body,sort_keys=True)+'\n');stream.flush();os.fsync(stream.fileno())
fd=os.open(path.parent,os.O_DIRECTORY)
try:os.fsync(fd)
finally:os.close(fd)
PY
  git -C "$ROOT/markets" checkout -q --detach "$MARKETS_SHA" || return 2
  resolved="$(git -C "$ROOT/markets" rev-parse HEAD)" || return 2
  [ "$resolved" = "$MARKETS_SHA" ] || { echo "checkout differs from the dispatch pin; intent retained"; return 2; }
  "$ROOT/venv/bin/python" - "$intent" "$receipt" "$resolved" <<'PY' || return 2
import hashlib, json, os, pathlib, sys
intent,path=pathlib.Path(sys.argv[1]),pathlib.Path(sys.argv[2])
body=dict(schema='FRANKIE_MARKETS_CHECKOUT_RECEIPT_V1',intent=str(intent),
    intent_sha256=hashlib.sha256(intent.read_bytes()).hexdigest(),actual_commit=sys.argv[3])
with path.open('x',encoding='utf-8') as stream:
    stream.write(json.dumps(body,sort_keys=True)+'\n');stream.flush();os.fsync(stream.fileno())
fd=os.open(path.parent,os.O_DIRECTORY)
try:os.fsync(fd)
finally:os.close(fd)
PY
  echo "markets HEAD $resolved; checkout receipt $receipt"
}

preflight() {
  # The engine is the BOSS: the retained Granite vLLM on Pod g7y3g2w1kor4l3 over jobs_v1 (frankie_box_boss_session.py).
  # Verifies the request against the authored source contract, computes the timing labels by code, reads the Pod
  # record through the SecureString /markets/frankie/granite-service (never printed) and probes /health. Starts nothing.
  echo "engine: BOSS (retained Granite vLLM, jobs_v1; frankie_box_boss_session.py --stage preflight)"
  checkout_markets || return 2
  "$ROOT/venv/bin/python" "$ROOT/markets/deploy/aws/box/frankie_box_boss_session.py" --session "$S" --day "$DAY" --cycle "$CYCLE" --stage preflight
}
verify() {
  echo "### verify (no session started): request digest through the adapter, the task document, the pusher's token reach"
  checkout_markets || return 2
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
start_session() {
    if systemctl is-active --quiet "$UNIT.service"; then echo "$UNIT is already running; not restarting (Greg's word)"; status; return 0; fi
    [ -s "$ROOT/request/session-request.json" ] || { echo "request not on the box"; return 2; }
    [ -x "$ROOT/venv/bin/python" ] || { echo "venv not staged"; return 2; }
    checkout_markets || return 2
    TASK="$ROOT/markets/research/kalshi/frankie_boss/operations/ROOT_CYCLE_00_TASK_20260920.md"; [ -s "$TASK" ] || { echo "task document missing at $TASK"; return 2; }
    preflight || return 3
    "$ROOT/venv/bin/python" -c "
import json,sys; sys.path.insert(0,'$ROOT/markets')
from research.kalshi.frankie_boss.frankie_principal_adapter import digest
print(digest(json.loads(open('$ROOT/request/session-request.json','rb').read())))" > "$S/request_sha256" || { echo "request digest failed"; return 2; }
    echo "request_sha256 $(cat "$S/request_sha256")"
    if [ -e "$S/done" ] || [ -L "$S/done" ]; then
      "$ROOT/venv/bin/python" - "$ROOT" "$S/done" <<'PY' || return 2
import pathlib, sys
root,path=pathlib.Path(sys.argv[1]),pathlib.Path(sys.argv[2])
if path.is_symlink() or not path.is_file():raise SystemExit('completion marker must be a regular file')
sys.path.insert(0,str(root/'markets'))
from deploy.aws.box.frankie_box_classroom_cache import preserve
preserve(path,'new explicitly started session retains the preceding completion marker')
PY
    fi
    echo "verified" > "$S/phase"; echo "request and data plane verified on the box; session starting" > "$S/note"
    systemctl reset-failed "frankie-heartbeat-$CYCLE.service" 2>/dev/null
    systemd-run --unit "frankie-heartbeat-$CYCLE" --collect -p WorkingDirectory="$S" -p StandardOutput=append:"$ROOT/logs/heartbeat-$CYCLE.log" -p StandardError=append:"$ROOT/logs/heartbeat-$CYCLE.log" \
      "$ROOT/venv/bin/python" "$ROOT/markets/deploy/aws/box/frankie_box_heartbeat.py" --session "$S" --day "$DAY" --cycle "$CYCLE" --base "$MARKETS_SHA" >/dev/null 2>&1 || echo "heartbeat service start failed"
    systemctl reset-failed "$UNIT.service" 2>/dev/null
    systemd-run --unit "$UNIT" --collect -p WorkingDirectory="$S" -p StandardOutput=append:"$ROOT/logs/session-$CYCLE.log" -p StandardError=append:"$ROOT/logs/session-$CYCLE.log" \
      "$ROOT/venv/bin/python" "$ROOT/markets/deploy/aws/box/frankie_box_boss_session.py" --session "$S" --day "$DAY" --cycle "$CYCLE" --stage run >/dev/null 2>&1 \
      && echo "$UNIT started (the BOSS session; hours; watch the heartbeat and the session log)" || { echo "$UNIT start failed"; return 3; }
    sleep 5
    status
}
derive_only() {
  # Checkpoint E (PLAN_CYCLE0_BEDROCK_20260921.md, on Greg's go; box only, no model call): verify + labels + derive (the
  # legacy five and the bedrock through the pinned producers) + the DIGEST_V6 + its token/part measurement, in the
  # foreground under this SSM command. Refuses while the cycle session unit runs (its checkout would move under it).
  for U in "$UNIT" "frankie-heartbeat-$CYCLE" "frankie-correction-$CYCLE"; do
    if systemctl is-active --quiet "$U.service"; then echo "$U is running: derive_only waits (its checkout would move the code under the running unit)"; return 2; fi
  done
  checkout_markets || return 2
  echo "markets HEAD $(git -C "$ROOT/markets" rev-parse HEAD) ($MARKETS_SHA)"
  echo "producers HEAD $(git -C "$ROOT/producers" rev-parse HEAD 2>/dev/null || echo missing)"
  "$ROOT/venv/bin/python" "$ROOT/markets/deploy/aws/box/frankie_box_boss_session.py" --session "$S" --day "$DAY" --cycle "$CYCLE" --stage derive_only || { echo "derive_only failed (exit $?)"; return 3; }
  M="$S/work/derive-only-measurement.json"; [ "$CYCLE" = "00" ] || M="$S/work-$CYCLE/derive-only-measurement.json"
  [ -s "$M" ] && { echo "### derive-only measurement (markets HEAD $(git -C "$ROOT/markets" rev-parse HEAD))"; cat "$M"; }
}
fetch_correction() {
  # The host's retained classroom-correction-request.json, exported by frankie_host_export_principal_request.yml
  # (turn=correction) and presigned by frankie_box_run.yml (presign=<bucket>/<key>) into the private map at MAP_URL.
  # Fetched into request/, sha256 printed; an existing file with different bytes is never overwritten.
  [ -n "${MAP_URL:-}" ] || { echo "fetch_correction needs MAP_URL (frankie_box_run.yml presign=<bucket>/<key of classroom-correction-request.json>)"; return 2; }
  mkdir -p "$ROOT/tmp" "$ROOT/request"
  curl -fsS -m 60 --retry 3 -o "$ROOT/tmp/presigned-map.json" "$MAP_URL" || { echo "presigned map download failed"; return 2; }
  export ROOT
  trap 'rm -f "$ROOT/tmp/presigned-map.json"' RETURN      # the presigned URLs do not stay on the disk
  "$ROOT/venv/bin/python" - <<'PY' || return 2
import hashlib, json, os, subprocess
root = os.environ['ROOT']
m = json.load(open(os.path.join(root, 'tmp', 'presigned-map.json')))
keys = [k for k in m if k.endswith('/classroom-correction-request.json') or k == 'classroom-correction-request.json']
if len(keys) != 1: raise SystemExit(f'the map must carry exactly one classroom-correction-request.json key ({len(keys)} found)')
target = os.path.join(root, 'request', 'classroom-correction-request.json'); tmp = target + '.part'
r = subprocess.run(['curl', '-fsS', '-m', '300', '--retry', '3', '-o', tmp, m[keys[0]]['url']], capture_output=True, text=True)
if r.returncode: raise SystemExit(f'download failed: curl exit {r.returncode}')
data = open(tmp, 'rb').read()
if 'bytes' in m[keys[0]] and int(m[keys[0]]['bytes']) != len(data): os.unlink(tmp); raise SystemExit(f'downloaded {len(data)} bytes, the map says {m[keys[0]]["bytes"]}')
doc = json.loads(data)
if doc.get('schema') != 'FRANKIE_DIPOLE_CLASSROOM_CORRECTION_REQUEST_V1': os.unlink(tmp); raise SystemExit('the downloaded file is not a Dipole classroom correction request')
response_path = os.path.join(root, 'session', 'out', 'response.json')
if os.path.exists(response_path):
    answered = json.load(open(response_path, 'rb')).get('request_sha256')
    if doc.get('original_request_sha256') != answered:
        os.unlink(tmp); raise SystemExit(f'the correction request answers principal request {str(doc.get("original_request_sha256"))[:16]}, this box answered {str(answered)[:16]}; not taken')
if os.path.exists(target) and open(target, 'rb').read() != data:
    os.unlink(tmp); raise SystemExit('a different classroom-correction-request.json is already on the box; not overwritten (move it aside with a receipt first)')
os.replace(tmp, target)
print(f'CORRECTION_REQUEST key={keys[0]} bytes={len(data)} sha256={hashlib.sha256(data).hexdigest()} request_sha256={doc.get("request_sha256")} correction_ids={len(doc.get("correction_ids", []))} session_id={doc.get("session_id")}')
PY
}
correction() {
  # The same session's turn 2 (frankie_box_boss_session.py --stage correction) as its own transient unit: one BOSS call,
  # the three correction files into out/, then the pusher with TURN=correction. Requires the fetched request and the
  # response this session wrote. Never touches the cycle session unit.
  U="frankie-correction-$CYCLE"
  if systemctl is-active --quiet "$U.service"; then echo "$U is already running"; status; return 0; fi
  if systemctl is-active --quiet "$UNIT.service"; then echo "$UNIT is running: the correction waits (its checkout would move the code under the running session)"; return 2; fi
  [ -s "$ROOT/request/classroom-correction-request.json" ] || { echo "no correction request on the box (ACTION=fetch_correction first)"; return 2; }
  [ -s "$S/out/response.json" ] || { echo "no out/response.json: the correction belongs to the session that wrote the response"; return 2; }
  checkout_markets || return 2
  systemctl reset-failed "$U.service" 2>/dev/null
  systemd-run --unit "$U" --collect -p WorkingDirectory="$S" -p StandardOutput=append:"$ROOT/logs/correction-$CYCLE.log" -p StandardError=append:"$ROOT/logs/correction-$CYCLE.log" \
    "$ROOT/venv/bin/python" "$ROOT/markets/deploy/aws/box/frankie_box_boss_session.py" --session "$S" --day "$DAY" --cycle "$CYCLE" --stage correction >/dev/null 2>&1 \
    && echo "$U started (the correction turn on the BOSS; minutes; watch logs/correction-$CYCLE.log)" || { echo "$U start failed"; return 3; }
  sleep 5
  status
}
case "$ACTION" in
  status) status ;;
  fetch_correction) fetch_correction ;;
  correction) correction ;;
  derive_only) derive_only ;;
  preflight) preflight ;;
  verify) verify ;;
  start) start_session ;;
  restart_session)
    # Stops ONLY the session unit (never the heartbeat, never a Pod or a box) to apply a session-code fix, with a receipt,
    # then starts it again; every stage resumes from its receipts under session/work/. An explicit operator action.
    echo "### restart_session: stopping $UNIT only (receipted), then start"
    if systemctl is-active --quiet "$UNIT.service"; then
      systemctl stop "$UNIT.service" && echo "$UNIT stopped"
      printf '{"schema":"FRANKIE_BOX_SESSION_RESTART_RECEIPT_V1","at":%s,"unit":"%s","reason":"session-code fix (%s); stages resume from receipts","phase_before":"%s"}\n' \
        "$(date +%s)" "$UNIT" "${REASON:-unstated}" "$(cat "$S/phase" 2>/dev/null || echo -)" > "$ROOT/receipts/session-restart-$(date +%s).json"
    else echo "$UNIT was not running"; fi
    systemctl reset-failed "$UNIT.service" 2>/dev/null
    start_session ;;
  *) echo "ACTION must be start, status, preflight, verify, restart_session, fetch_correction, correction or derive_only"; exit 2 ;;
esac
