# Job 0 step 4 (delivery): push Frankie's four cycle files from his box to root/cycle-<NN>-response.
# Reads /opt/frankie-box/session/out/{response.json,analysis.md,host-session-record.json,host-attestation.json},
# runs the same shape and binding checks the recorder workflow runs (so a refusal happens here, not there), and pushes
# them under research/kalshi/frankie_boss/runs/<day>/root/ on a branch cut from BASE. The token comes from SSM
# SecureString /markets/frankie/github-token (us-east-2) into this process only. Idempotent; never force-pushes.
# Inputs: DAY (20211003), CYCLE (00), BASE (this branch); MAP_URL (optional, set by frankie_box_fetch_response.yml) selects
# the token-free route: the files are uploaded through presigned PUTs and that workflow commits them.
set -u
ROOT=/opt/frankie-box; OUT="$ROOT/session/out"
DAY="${DAY:-20211003}"; CYCLE="${CYCLE:-00}"; BASE="${BASE:-claude/cycle-0-frankie-box-rerun-od5sxk}"
export HOME=/root GIT_TERMINAL_PROMPT=0
TURN="${TURN:-initial}"      # initial = the four cycle files; correction = the three Dipole classroom correction files (turn 2, 2026-09-21)
DOCS_ONLY="${DOCS_ONLY:-0}"   # 1 = publish only out/docs (built here from the session work directory) under runs/<day>/root/docs-cycle-<NN>/
BRAIN_ONLY="${BRAIN_ONLY:-0}" # 1 = build this cycle's brain entry (digest, accounting + ledgers, analysis) from work + out and publish it under runs/<day>/root/brain/cycle-<NN>/
[ "$BRAIN_ONLY" = "1" ] && DOCS_ONLY=1   # same token-only, four-files-untouched path
if [ "$DOCS_ONLY" = "1" ] && [ -n "${MAP_URL:-}" ]; then echo "DOCS_ONLY publishes through the token route only (no MAP_URL)"; exit 2; fi
if [ "$DOCS_ONLY" = "1" ]; then
  # The docs module comes from BASE by a fetch (FETCH_HEAD only): the box's checkout, which a running session may be
  # using, is never moved by this mode. Reads the session work directory; writes only out/docs.
  WORKDIR="$ROOT/session/$([ "$CYCLE" = "00" ] && echo work || echo "work-$CYCLE")"
  mkdir -p "$ROOT/tmp"
  git -C "$ROOT/markets" fetch -q --depth 1 origin "$BASE" && git -C "$ROOT/markets" show FETCH_HEAD:deploy/aws/box/frankie_box_docs.py > "$ROOT/tmp/frankie_box_docs.py" || { echo "cannot fetch frankie_box_docs.py from $BASE"; exit 2; }
  echo "docs module from $BASE $(git -C "$ROOT/markets" rev-parse --short FETCH_HEAD), sha256 $(sha256sum "$ROOT/tmp/frankie_box_docs.py" | cut -c1-16); work $WORKDIR"
  if [ "$BRAIN_ONLY" = "1" ]; then
    git -C "$ROOT/markets" show FETCH_HEAD:deploy/aws/box/frankie_box_brain.py > "$ROOT/tmp/frankie_box_brain.py" || { echo "cannot fetch frankie_box_brain.py from $BASE"; exit 2; }
    "$ROOT/venv/bin/python" "$ROOT/tmp/frankie_box_brain.py" --work "$WORKDIR" --out "$OUT" --brain "$ROOT/brain" --cycle "$CYCLE" || { echo "brain entry failed"; exit 2; }
  else
    "$ROOT/venv/bin/python" "$ROOT/tmp/frankie_box_docs.py" --work "$WORKDIR" --out "$OUT/docs" --cycle "$CYCLE" || { echo "docs build failed"; exit 2; }
  fi
else
  case "$TURN" in initial) FILES="response.json analysis.md host-session-record.json host-attestation.json" ;; correction) FILES="correction-response.json host-correction-record.json host-correction-attestation.json" ;; *) echo "TURN must be initial or correction"; exit 2 ;; esac
  for f in $FILES; do [ -s "$OUT/$f" ] || { echo "missing $OUT/$f"; exit 2; }; done
fi
export OUT ROOT TURN
if [ "$DOCS_ONLY" != "1" ] && [ "$TURN" = "correction" ]; then "$ROOT/venv/bin/python" - <<'PY' || exit 1
import hashlib, json, os, sys
out = os.environ['OUT']
raw = {n: open(os.path.join(out, n), 'rb').read() for n in ('correction-response.json', 'host-correction-record.json', 'host-correction-attestation.json')}
r = json.loads(raw['correction-response.json']); rec = json.loads(raw['host-correction-record.json']); a = json.loads(raw['host-correction-attestation.json'])
for k in ('request_sha256', 'session_id', 'model_identity_as_reported_by_session', 'dipole_acknowledgement'):
    if k not in r: sys.exit(f'correction-response.json lacks {k}')
ack = r['dipole_acknowledgement']
if ack.get('acknowledged') is not True or not isinstance(ack.get('correction_resolutions'), list): sys.exit('the acknowledgement must carry acknowledged true and correction_resolutions')
def digest(value): return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
correction = json.loads(open(os.path.join(os.environ['ROOT'], 'request', 'classroom-correction-request.json'), 'rb').read())
if r['request_sha256'] != correction.get('request_sha256'): sys.exit("correction-response.request_sha256 is not the correction request's request_sha256 on this box")
if rec.get('request_sha256') != digest(correction): sys.exit('host-correction-record.request_sha256 is not the adapter digest of the whole correction request')
if rec.get('response_sha256') != digest(r): sys.exit('host-correction-record.response_sha256 is not digest(correction-response)')
if rec.get('schema') != 'FRANKIE_HOST_AGENT_SESSION_ATTESTATION_V1' or rec.get('mechanism') != 'AGENT_SESSION' or not rec.get('host_authority'): sys.exit('host-correction-record schema/mechanism/host_authority')
resp = json.loads(open(os.path.join(out, 'response.json'), 'rb').read()) if os.path.exists(os.path.join(out, 'response.json')) else {}
for k in ('session_id', 'model_identity_as_reported_by_session'):
    if resp and r[k] != resp.get(k): sys.exit(f'correction-response.{k} differs from the response this session wrote')
w = rec.get('response') or {}
if w.get('sha256') != hashlib.sha256(raw['correction-response.json']).hexdigest() or int(w.get('bytes', -1)) != len(raw['correction-response.json']): sys.exit('host-correction-record.response witness differs from the file')
for k in ('schema', 'mechanism', 'request_sha256', 'response_sha256', 'session_id', 'model_identity_as_reported_by_session'):
    if a.get(k) != rec.get(k): sys.exit(f'attestation.{k} differs from the record')
hr = a.get('host_record') or {}
if set(hr) != {'path', 'bytes', 'sha256'} or hr['sha256'] != hashlib.sha256(raw['host-correction-record.json']).hexdigest() or int(hr['bytes']) != len(raw['host-correction-record.json']): sys.exit('attestation.host_record must pin the record file {path, bytes, sha256}')
if not hr['path'].endswith('/principal/host-correction-record.json'): sys.exit('attestation.host_record.path must name principal/host-correction-record.json on the host')
print('correction shape and binding checks: OK'); print({n: (len(b), hashlib.sha256(b).hexdigest()) for n, b in raw.items()})
PY
fi
[ "$DOCS_ONLY" = "1" ] || [ "$TURN" = "correction" ] || "$ROOT/venv/bin/python" - <<'PY' || exit 1
import hashlib, json, os, sys
out = os.environ['OUT']
raw = {n: open(os.path.join(out, n), 'rb').read() for n in ('response.json', 'host-session-record.json', 'host-attestation.json', 'analysis.md')}
r = json.loads(raw['response.json']); rec = json.loads(raw['host-session-record.json']); a = json.loads(raw['host-attestation.json'])
for k in ('request_sha256', 'session_id', 'model_identity_as_reported_by_session', 'sections', 'feedback', 'lessons'):
    if k not in r: sys.exit(f'response.json lacks {k}')
if len(r['sections']) != 18: sys.exit('response.sections must carry the 18 section ids')
if 'principal_receipt_hash' in json.dumps(r['feedback']): sys.exit('feedback must carry NO principal_receipt_hash')
if not isinstance(r['lessons'], list) or not r['lessons']: sys.exit('lessons must be a nonempty list')
sys.path.insert(0, os.path.join(os.environ['ROOT'], 'markets'))
from research.kalshi.frankie_boss.frankie_principal_adapter import digest
req = json.loads(open(os.path.join(os.environ['ROOT'], 'request', 'session-request.json'), 'rb').read())
if r['request_sha256'] != digest(req): sys.exit('response.request_sha256 is not the adapter digest of the request on this box')
if rec.get('schema') != 'FRANKIE_HOST_AGENT_SESSION_ATTESTATION_V1' or rec.get('mechanism') != 'AGENT_SESSION': sys.exit('host-session-record schema/mechanism')
if rec.get('response_sha256') != digest(r): sys.exit('host-session-record.response_sha256 is not digest(response)')
if not rec.get('host_authority'): sys.exit('host_authority must be nonempty')
for wname, fname in (('response', 'response.json'), ('analysis', 'analysis.md')):
    w = rec.get(wname) or {}
    if w.get('sha256') != hashlib.sha256(raw[fname]).hexdigest() or int(w.get('bytes', -1)) != len(raw[fname]): sys.exit(f'host-session-record.{wname} witness differs from the file')
for k in ('schema', 'mechanism', 'request_sha256', 'response_sha256', 'session_id', 'model_identity_as_reported_by_session'):
    if a.get(k) != rec.get(k): sys.exit(f'attestation.{k} differs from the record')
hr = a.get('host_record') or {}
if set(hr) != {'path', 'bytes', 'sha256'} or hr['sha256'] != hashlib.sha256(raw['host-session-record.json']).hexdigest() or int(hr['bytes']) != len(raw['host-session-record.json']): sys.exit('attestation.host_record must pin the record file {path, bytes, sha256}')
print('shape and binding checks: OK'); print({n: (len(b), hashlib.sha256(b).hexdigest()) for n, b in raw.items()})
PY
if [ -n "${MAP_URL:-}" ]; then
  # Token-free route (2026-09-21; Greg's git token is not on the box yet): frankie_box_fetch_response.yml signed one
  # short-lived presigned PUT per file into a private map reachable only through MAP_URL. The four files, already
  # checked above, are uploaded there and THAT WORKFLOW commits them to root/cycle-<NN>-response with its own
  # credentials after re-running the same checks on what it downloaded. The box's role touches nothing in S3 and no
  # URL is printed; a receipt with every file's size and sha256 is written beside the push receipts.
  T="$ROOT/tmp"; mkdir -p "$T"
  curl -fsS -m 60 --retry 3 -o "$T/response-upload-map.json" "$MAP_URL" || { echo "upload map download failed"; exit 2; }
  export T
  trap 'rm -f "$T/response-upload-map.json"' EXIT      # the presigned URLs do not stay on the disk
  "$ROOT/venv/bin/python" - <<'PY' || exit 5
import hashlib, json, os, subprocess, time
out, t, root = os.environ['OUT'], os.environ['T'], os.environ['ROOT']
m = json.load(open(os.path.join(t, 'response-upload-map.json')))
files = ('response.json', 'analysis.md', 'host-session-record.json', 'host-attestation.json') if os.environ.get('TURN', 'initial') == 'initial' else ('correction-response.json', 'host-correction-record.json', 'host-correction-attestation.json')
missing = [n for n in files if n not in m or not m[n].get('url')]
if missing: raise SystemExit(f'upload map lacks {missing}')
receipt = {}
for n in files:
    path = os.path.join(out, n); data = open(path, 'rb').read(); url = m[n]['url']
    r = subprocess.run(['curl', '-fsS', '-m', '600', '--retry', '3', '-T', path, url], capture_output=True, text=True)
    if r.returncode: raise SystemExit(f'upload of {n} failed: curl exit {r.returncode}: {r.stderr[-300:].replace(url, "<url>")}')
    receipt[n] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), bucket=m[n].get('bucket'), key=m[n].get('key'))
    print(f'uploaded {n}: {len(data)} bytes, sha256 {receipt[n]["sha256"]}')
rec = dict(schema='FRANKIE_BOX_RESPONSE_UPLOAD_RECEIPT_V1', at=int(time.time()), route='presigned-put', turn=os.environ.get('TURN', 'initial'), files=receipt)
open(os.path.join(root, 'receipts', f'response-upload-{rec["at"]}.json'), 'w').write(json.dumps(rec, sort_keys=True) + '\n')
print('UPLOAD_RECEIPT ' + json.dumps(rec, sort_keys=True))
PY
  echo "uploaded through the presigned map; frankie_box_fetch_response.yml now re-checks and commits root/cycle-$CYCLE-response"
  exit 0
fi
TOKEN=$("$ROOT/venv/bin/python" -c "import boto3;print(boto3.client('ssm',region_name='us-east-2').get_parameter(Name='/markets/frankie/github-token',WithDecryption=True)['Parameter']['Value'])" 2>/dev/null) || { echo "no push token readable at /markets/frankie/github-token (us-east-2); files are ready in $OUT, push refused"; exit 3; }
export FRANKIE_GIT_TOKEN="$TOKEN"; unset TOKEN
HELPER='!f() { echo username=x-access-token; echo "password=$FRANKIE_GIT_TOKEN"; }; f'
W="$ROOT/session/response-clone"; BR="root/cycle-$CYCLE-response"; DEST="research/kalshi/frankie_boss/runs/$DAY/root"
[ -d "$W/.git" ] || git clone -q --depth 1 --branch "$BASE" https://github.com/DavisAI1974/Markets.git "$W" || exit 2
cd "$W" || exit 2
git fetch -q origin "$BR" 2>/dev/null && git checkout -q -B "$BR" FETCH_HEAD || git checkout -q -B "$BR"
mkdir -p "$DEST"
if [ "$DOCS_ONLY" != "1" ]; then for f in $FILES; do cp "$OUT/$f" "$DEST"/; done; fi
if [ "$BRAIN_ONLY" != "1" ] && [ -d "$OUT/docs" ]; then mkdir -p "$DEST/docs-cycle-$CYCLE"; cp "$OUT"/docs/*.md "$OUT"/docs/docs-index.json "$DEST/docs-cycle-$CYCLE"/ && echo "docs: $(ls "$OUT"/docs | wc -l) files -> $DEST/docs-cycle-$CYCLE"; fi
if [ -d "$ROOT/brain/cycle-$CYCLE" ]; then mkdir -p "$DEST/brain/cycle-$CYCLE"; cp "$ROOT/brain/cycle-$CYCLE"/* "$DEST/brain/cycle-$CYCLE"/ && echo "brain: cycle $CYCLE entry ($(ls "$ROOT/brain/cycle-$CYCLE" | wc -l) files) -> $DEST/brain/cycle-$CYCLE"; fi
git add "$DEST"
if [ "$TURN" = "correction" ]; then MSG="root: cycle $CYCLE Frankie Dipole classroom correction response, host correction record and attestation (from Frankie's box i-035994afa8bdf66a5; the same session's turn 2)"; elif [ "$BRAIN_ONLY" = "1" ]; then MSG="root: cycle $CYCLE brain entry (derivation digest, accounting and ledgers, analysis; Frankie's calculation findings carried forward)"; elif [ "$DOCS_ONLY" = "1" ]; then MSG="root: cycle $CYCLE session documents as Markdown (reading notes, merges, merged notes, derivation digest, receipts; from Frankie's box)"; else MSG="root: cycle $CYCLE Frankie response, attestation, host session record, analysis, session documents (from Frankie's box i-035994afa8bdf66a5; request_sha256 per response.json)"; fi
git -c user.name=frankie-box -c user.email=frankie-box@markets.local commit -q -m "$MSG" || echo "(nothing new to commit)"
git -c credential.helper="$HELPER" push -q origin "HEAD:$BR" || { echo "push failed"; exit 4; }
unset FRANKIE_GIT_TOKEN
git log --oneline -1; git ls-remote origin "$BR"
sha=$(git rev-parse HEAD)
files_json=$(printf '%s\n' ${FILES:-docs} | python3 -c 'import json,sys; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')
printf '{"schema":"FRANKIE_BOX_RESPONSE_PUSH_RECEIPT_V1","at":%s,"branch":"%s","commit":"%s","turn":"%s","files":%s}\n' "$(date +%s)" "$BR" "$sha" "$TURN" "$files_json" > "$ROOT/receipts/response-push-$(date +%s).json"
echo "pushed $BR at $sha; next: frankie_host_record_principal_response.yml source_ref=$BR turn=$TURN"
