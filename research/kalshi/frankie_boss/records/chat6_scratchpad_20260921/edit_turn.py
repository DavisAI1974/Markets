from pathlib import Path
import os
os.chdir('/home/user/Markets')

# ---- A. export workflow + host script: turn ----
Y = Path('.github/workflows/frankie_host_export_principal_request.yml'); y = Y.read_text()
old = "      cycle_index:\n        description: 'Zero-padded cycle index'\n        required: false\n        default: '00'\n      instance:"
new = "      cycle_index:\n        description: 'Zero-padded cycle index'\n        required: false\n        default: '00'\n      turn:\n        description: 'initial = session-request.json + prompt.md + historical-prompt.md; correction = the retained classroom-correction-request.json only (the Dipole classroom turn 2, for the box)'\n        required: false\n        default: 'initial'\n        type: choice\n        options: ['initial', 'correction']\n      instance:"
assert old in y; y = y.replace(old, new, 1)
old = "        env:\n          DAY: ${{ inputs.day }}\n          CYCLE_INDEX: ${{ inputs.cycle_index }}\n          BUCKET: ${{ inputs.bucket }}\n        run: |\n          python - <<'PY'\n          import os\n          from pathlib import Path\n          import boto3\n          from botocore.config import Config\n          s3 = boto3.client('s3', region_name='us-east-1', config=Config(signature_version='s3v4'))\n          prefix = f\"host-deliveries/{os.environ['DAY']}/principal-request/cycle-{os.environ['CYCLE_INDEX']}/{os.environ['GITHUB_RUN_ID']}\"\n          for name in ('session-request.json', 'prompt.md', 'historical-prompt.md'):\n"
new = "        env:\n          DAY: ${{ inputs.day }}\n          CYCLE_INDEX: ${{ inputs.cycle_index }}\n          BUCKET: ${{ inputs.bucket }}\n          TURN: ${{ inputs.turn }}\n        run: |\n          [[ \"$TURN\" =~ ^(initial|correction)$ ]] || { echo \"turn must be initial or correction\"; exit 1; }\n          python - <<'PY'\n          import os\n          from pathlib import Path\n          import boto3\n          from botocore.config import Config\n          s3 = boto3.client('s3', region_name='us-east-1', config=Config(signature_version='s3v4'))\n          prefix = f\"host-deliveries/{os.environ['DAY']}/principal-request/cycle-{os.environ['CYCLE_INDEX']}/{os.environ['GITHUB_RUN_ID']}\"\n          names = ('session-request.json', 'prompt.md', 'historical-prompt.md') if os.environ['TURN'] == 'initial' else ('classroom-correction-request.json',)\n          for name in names:\n"
assert old in y; y = y.replace(old, new, 1)
old = "          RUN_ROOT: ${{ inputs.run_root }}\n          CYCLE_INDEX: ${{ inputs.cycle_index }}\n        run: |\n          python deploy/aws/ssm_run_ps1.py \\\n            --instance \"$INSTANCE\" --region us-east-2 \\\n            --script deploy/aws/host/frankie_host_export_principal_request.ps1 \\\n            --set \"Day=$DAY\" \\\n            --set \"RunRoot=$RUN_ROOT\" \\\n            --set \"CycleIndex=$CYCLE_INDEX\" \\\n            --set \"RequestUrl=$(cat \"$RUNNER_TEMP/session-request.json.url\")\" \\\n            --set \"PromptUrl=$(cat \"$RUNNER_TEMP/prompt.md.url\")\" \\\n            --set \"HistoricalUrl=$(cat \"$RUNNER_TEMP/historical-prompt.md.url\")\" \\\n            --timeout 900 --tail 0 --comment \"export the cycle $CYCLE_INDEX principal request for day $DAY\" | tee \"$RUNNER_TEMP/export.log\"\n"
new = "          RUN_ROOT: ${{ inputs.run_root }}\n          CYCLE_INDEX: ${{ inputs.cycle_index }}\n          TURN: ${{ inputs.turn }}\n        run: |\n          set -euo pipefail\n          if [ \"$TURN\" = initial ]; then\n            urls=(--set \"RequestUrl=$(cat \"$RUNNER_TEMP/session-request.json.url\")\" --set \"PromptUrl=$(cat \"$RUNNER_TEMP/prompt.md.url\")\" --set \"HistoricalUrl=$(cat \"$RUNNER_TEMP/historical-prompt.md.url\")\")\n          else\n            urls=(--set \"RequestUrl=$(cat \"$RUNNER_TEMP/classroom-correction-request.json.url\")\")\n          fi\n          python deploy/aws/ssm_run_ps1.py \\\n            --instance \"$INSTANCE\" --region us-east-2 \\\n            --script deploy/aws/host/frankie_host_export_principal_request.ps1 \\\n            --set \"Day=$DAY\" \\\n            --set \"RunRoot=$RUN_ROOT\" \\\n            --set \"CycleIndex=$CYCLE_INDEX\" \\\n            --set \"Turn=$TURN\" \\\n            \"${urls[@]}\" \\\n            --timeout 900 --tail 0 --comment \"export the cycle $CYCLE_INDEX principal request ($TURN) for day $DAY\" | tee \"$RUNNER_TEMP/export.log\"\n"
assert old in y; y = y.replace(old, new, 1)
old = "        env:\n          BUCKET: ${{ inputs.bucket }}\n          PREFIX: ${{ steps.sign.outputs.prefix }}\n        run: |\n          python - <<'PY'\n          import hashlib, os, re\n          from pathlib import Path\n          import boto3\n          log = Path(os.environ['RUNNER_TEMP'], 'export.log').read_text()\n          printed = {m.group(1): (int(m.group(2)), m.group(3)) for m in re.finditer(r'EXPORTED (\\S+) bytes=(\\d+) sha256=([0-9a-f]{64})', log)}\n          if set(printed) != {'session-request.json', 'prompt.md', 'historical-prompt.md'}:\n              raise SystemExit(f'host printed hashes for {sorted(printed)}, not all three files')\n"
new = "        env:\n          BUCKET: ${{ inputs.bucket }}\n          PREFIX: ${{ steps.sign.outputs.prefix }}\n          TURN: ${{ inputs.turn }}\n        run: |\n          python - <<'PY'\n          import hashlib, os, re\n          from pathlib import Path\n          import boto3\n          log = Path(os.environ['RUNNER_TEMP'], 'export.log').read_text()\n          printed = {m.group(1): (int(m.group(2)), m.group(3)) for m in re.finditer(r'EXPORTED (\\S+) bytes=(\\d+) sha256=([0-9a-f]{64})', log)}\n          expected = {'session-request.json', 'prompt.md', 'historical-prompt.md'} if os.environ['TURN'] == 'initial' else {'classroom-correction-request.json'}\n          if set(printed) != expected:\n              raise SystemExit(f'host printed hashes for {sorted(printed)}, not {sorted(expected)}')\n"
assert old in y; y = y.replace(old, new, 1)
old = "          print('Root downloads these three with the AWS pair on the box and verifies the sha256 of each before reading.')\n"
new = "          print('The box fetches these by key (frankie_box_run.yml presign=<bucket/key>; frankie_box_session.sh ACTION=fetch_correction for the correction turn) and verifies the sha256 of each before reading.')\n"
assert old in y; y = y.replace(old, new, 1)
Y.write_text(y)

P = Path('deploy/aws/host/frankie_host_export_principal_request.ps1'); t = P.read_text()
old = "foreach ($required in 'Day', 'RunRoot', 'CycleIndex', 'RequestUrl', 'PromptUrl', 'HistoricalUrl') {\n"
new = "$turnValue = Get-Variable -Name 'Turn' -ValueOnly -ErrorAction SilentlyContinue\nif (-not $turnValue -or $turnValue -like 'HOST_*') { $Turn = 'initial' }\nif ($Turn -notin @('initial', 'correction')) { throw \"Turn must be initial or correction (value: '$Turn')\" }\n# initial exports the three request files; correction exports the runner's retained classroom-correction-request.json\n# (the Dipole classroom turn 2, 2026-09-21) for the box to answer.\n$requiredNames = if ($Turn -eq 'initial') { @('Day', 'RunRoot', 'CycleIndex', 'RequestUrl', 'PromptUrl', 'HistoricalUrl') } else { @('Day', 'RunRoot', 'CycleIndex', 'RequestUrl') }\nforeach ($required in $requiredNames) {\n"
assert old in t; t = t.replace(old, new, 1)
old = "$files = [ordered]@{\n    'session-request.json' = $RequestUrl\n    'prompt.md'            = $PromptUrl\n    'historical-prompt.md' = $HistoricalUrl\n}\n"
new = "$files = [ordered]@{}\nif ($Turn -eq 'initial') {\n    $files['session-request.json'] = $RequestUrl\n    $files['prompt.md'] = $PromptUrl\n    $files['historical-prompt.md'] = $HistoricalUrl\n} else {\n    $files['classroom-correction-request.json'] = $RequestUrl\n}\n"
assert old in t; t = t.replace(old, new, 1)
old = "    schema      = 'FRANKIE_PRINCIPAL_REQUEST_EXPORTED_V1'\n    day         = $Day\n"
new = "    schema      = 'FRANKIE_PRINCIPAL_REQUEST_EXPORTED_V1'\n    turn        = $Turn\n    day         = $Day\n"
assert old in t; t = t.replace(old, new, 1)
P.write_text(t)

# ---- B. the push script: TURN ----
S = Path('deploy/aws/box/frankie_box_push_response.sh'); s = S.read_text()
old = "DOCS_ONLY=\"${DOCS_ONLY:-0}\"   # 1 = publish only out/docs"
new = "TURN=\"${TURN:-initial}\"      # initial = the four cycle files; correction = the three Dipole classroom correction files (turn 2, 2026-09-21)\nDOCS_ONLY=\"${DOCS_ONLY:-0}\"   # 1 = publish only out/docs"
assert old in s; s = s.replace(old, new, 1)
CORRECTION_CHECK = r'''import hashlib, json, os, sys
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
'''
old = "else\n  for f in response.json analysis.md host-session-record.json host-attestation.json; do [ -s \"$OUT/$f\" ] || { echo \"missing $OUT/$f\"; exit 2; }; done\nfi\nexport OUT ROOT\n[ \"$DOCS_ONLY\" = \"1\" ] || \"$ROOT/venv/bin/python\" - <<'PY' || exit 1\n"
new = ("else\n  case \"$TURN\" in initial) FILES=\"response.json analysis.md host-session-record.json host-attestation.json\" ;; correction) FILES=\"correction-response.json host-correction-record.json host-correction-attestation.json\" ;; *) echo \"TURN must be initial or correction\"; exit 2 ;; esac\n"
       "  for f in $FILES; do [ -s \"$OUT/$f\" ] || { echo \"missing $OUT/$f\"; exit 2; }; done\nfi\nexport OUT ROOT TURN\n"
       "if [ \"$DOCS_ONLY\" != \"1\" ] && [ \"$TURN\" = \"correction\" ]; then \"$ROOT/venv/bin/python\" - <<'PY' || exit 1\n" + CORRECTION_CHECK + "PY\nfi\n"
       "[ \"$DOCS_ONLY\" = \"1\" ] || [ \"$TURN\" = \"correction\" ] || \"$ROOT/venv/bin/python\" - <<'PY' || exit 1\n")
assert old in s; s = s.replace(old, new, 1)
old = "files = ('response.json', 'analysis.md', 'host-session-record.json', 'host-attestation.json')\nmissing = [n for n in files if n not in m or not m[n].get('url')]\n"
new = "files = ('response.json', 'analysis.md', 'host-session-record.json', 'host-attestation.json') if os.environ.get('TURN', 'initial') == 'initial' else ('correction-response.json', 'host-correction-record.json', 'host-correction-attestation.json')\nmissing = [n for n in files if n not in m or not m[n].get('url')]\n"
assert old in s; s = s.replace(old, new, 1)
old = "rec = dict(schema='FRANKIE_BOX_RESPONSE_UPLOAD_RECEIPT_V1', at=int(time.time()), route='presigned-put', files=receipt)\n"
new = "rec = dict(schema='FRANKIE_BOX_RESPONSE_UPLOAD_RECEIPT_V1', at=int(time.time()), route='presigned-put', turn=os.environ.get('TURN', 'initial'), files=receipt)\n"
assert old in s; s = s.replace(old, new, 1)
old = "[ \"$DOCS_ONLY\" = \"1\" ] || cp \"$OUT\"/response.json \"$OUT\"/host-attestation.json \"$OUT\"/host-session-record.json \"$OUT\"/analysis.md \"$DEST\"/\n"
new = "if [ \"$DOCS_ONLY\" != \"1\" ]; then for f in $FILES; do cp \"$OUT/$f\" \"$DEST\"/; done; fi\n"
assert old in s; s = s.replace(old, new, 1)
old = "if [ \"$BRAIN_ONLY\" = \"1\" ]; then MSG=\"root: cycle $CYCLE brain entry"
new = "if [ \"$TURN\" = \"correction\" ]; then MSG=\"root: cycle $CYCLE Frankie Dipole classroom correction response, host correction record and attestation (from Frankie's box i-035994afa8bdf66a5; the same session's turn 2)\"; elif [ \"$BRAIN_ONLY\" = \"1\" ]; then MSG=\"root: cycle $CYCLE brain entry"
assert old in s; s = s.replace(old, new, 1)
old = "printf '{\"schema\":\"FRANKIE_BOX_RESPONSE_PUSH_RECEIPT_V1\",\"at\":%s,\"branch\":\"%s\",\"commit\":\"%s\",\"files\":[\"response.json\",\"host-attestation.json\",\"host-session-record.json\",\"analysis.md\"]}\\n' \"$(date +%s)\" \"$BR\" \"$sha\" > \"$ROOT/receipts/response-push-$(date +%s).json\"\necho \"pushed $BR at $sha; next: frankie_host_record_principal_response.yml source_ref=$BR\""
new = "printf '{\"schema\":\"FRANKIE_BOX_RESPONSE_PUSH_RECEIPT_V1\",\"at\":%s,\"branch\":\"%s\",\"commit\":\"%s\",\"turn\":\"%s\",\"files\":\"%s\"}\\n' \"$(date +%s)\" \"$BR\" \"$sha\" \"$TURN\" \"${FILES:-docs}\" > \"$ROOT/receipts/response-push-$(date +%s).json\"\necho \"pushed $BR at $sha; next: frankie_host_record_principal_response.yml source_ref=$BR turn=$TURN\""
assert old in s; s = s.replace(old, new, 1)
S.write_text(s)

# ---- C. the fetch workflow: turn ----
F = Path('.github/workflows/frankie_box_fetch_response.yml'); f = F.read_text()
old = "      request_key:\n        description: 'Key of the session request the box answered (its adapter digest must equal response.request_sha256)'\n        required: false\n        default: 'host-deliveries/20211003/principal-request/cycle-00/35557744815/session-request.json'\n"
new = "      request_key:\n        description: 'initial: key of the session request the box answered (its adapter digest must equal response.request_sha256); correction: key of the exported classroom-correction-request.json the box answered'\n        required: false\n        default: 'host-deliveries/20211003/principal-request/cycle-00/35557744815/session-request.json'\n      turn:\n        description: 'initial = the four cycle files (response, analysis, host session record, attestation); correction = the three Dipole classroom correction files'\n        required: false\n        default: 'initial'\n        type: choice\n        options: ['initial', 'correction']\n"
assert old in f; f = f.replace(old, new, 1)
old = "      SCRIPT: deploy/aws/box/frankie_box_push_response.sh\n      FILES: response.json analysis.md host-session-record.json host-attestation.json\n"
new = "      SCRIPT: deploy/aws/box/frankie_box_push_response.sh\n      TURN: ${{ inputs.turn }}\n      FILES: ${{ inputs.turn == 'correction' && 'correction-response.json host-correction-record.json host-correction-attestation.json' || 'response.json analysis.md host-session-record.json host-attestation.json' }}\n"
assert old in f; f = f.replace(old, new, 1)
old = "          [[ \"$CYCLE\" =~ ^[0-9]{2}$ ]] || { echo \"cycle must be two digits\"; exit 1; }\n"
new = "          [[ \"$CYCLE\" =~ ^[0-9]{2}$ ]] || { echo \"cycle must be two digits\"; exit 1; }\n          [[ \"$TURN\" =~ ^(initial|correction)$ ]] || { echo \"turn must be initial or correction\"; exit 1; }\n          grep -q 'TURN=' \"$SCRIPT\" || { echo \"the pusher on this ref has no TURN route\"; exit 1; }\n"
assert old in f; f = f.replace(old, new, 1)
old = "          prefix = f\"host-deliveries/{os.environ['DAY']}/principal-response/cycle-{os.environ['CYCLE']}/box-upload/{run}\"\n"
new = "          prefix = f\"host-deliveries/{os.environ['DAY']}/principal-response/cycle-{os.environ['CYCLE']}/box-upload/{run}\" + ('' if os.environ['TURN'] == 'initial' else '/correction')\n"
assert old in f; f = f.replace(old, new, 1)
old = "            --set \"DAY=$DAY\" --set \"CYCLE=$CYCLE\" --set \"BASE=$GITHUB_REF_NAME\" --set \"MAP_URL=$MAP_URL\" | tee box-run-output.txt\n"
new = "            --set \"DAY=$DAY\" --set \"CYCLE=$CYCLE\" --set \"TURN=$TURN\" --set \"BASE=$GITHUB_REF_NAME\" --set \"MAP_URL=$MAP_URL\" | tee box-run-output.txt\n"
assert old in f; f = f.replace(old, new, 1)
old = "          # 2. the recorder's shape and binding checks, plus the analysis witness\n          r = json.loads(raw['response.json']); rec = json.loads(raw['host-session-record.json']); a = json.loads(raw['host-attestation.json'])\n          for k in ('request_sha256', 'session_id', 'model_identity_as_reported_by_session', 'sections', 'feedback', 'lessons'):\n              if k not in r: raise SystemExit(f'response lacks {k}')\n          if len(r['sections']) != 18: raise SystemExit(f\"response cites {len(r['sections'])} sections, not 18\")\n          if 'principal_receipt_hash' in json.dumps(r['feedback']): raise SystemExit('feedback must carry NO principal_receipt_hash')\n          if not isinstance(r['lessons'], list) or not r['lessons']: raise SystemExit('response carries no lessons')\n"
new = """          # 2. the recorder's shape and binding checks, plus the analysis witness
          def digest(value):
              return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
          turn = os.environ['TURN']
          if turn == 'correction':
              r = json.loads(raw['correction-response.json']); rec = json.loads(raw['host-correction-record.json']); a = json.loads(raw['host-correction-attestation.json'])
              for k in ('request_sha256', 'session_id', 'model_identity_as_reported_by_session', 'dipole_acknowledgement'):
                  if k not in r: raise SystemExit(f'correction response lacks {k}')
              if r['dipole_acknowledgement'].get('acknowledged') is not True: raise SystemExit('the acknowledgement is not acknowledged')
              if rec.get('schema') != 'FRANKIE_HOST_AGENT_SESSION_ATTESTATION_V1' or not rec.get('host_authority'): raise SystemExit('correction record schema/host_authority')
              if rec.get('response_sha256') != digest(r): raise SystemExit('record.response_sha256 is not the adapter digest of correction-response.json')
              w = rec.get('response') or {}
              if w.get('sha256') != hashlib.sha256(raw['correction-response.json']).hexdigest(): raise SystemExit('record.response witness differs from the file')
              for k in ('schema', 'mechanism', 'request_sha256', 'response_sha256', 'session_id', 'model_identity_as_reported_by_session'):
                  if a.get(k) != rec.get(k): raise SystemExit(f'attestation {k} differs from the record')
              hr = a.get('host_record') or {}
              if set(hr) != {'path', 'bytes', 'sha256'} or hr['sha256'] != hashlib.sha256(raw['host-correction-record.json']).hexdigest() or int(hr['bytes']) != len(raw['host-correction-record.json']):
                  raise SystemExit('attestation.host_record must pin the record file {path, bytes, sha256}')
              correction = json.loads(s3.get_object(Bucket=bucket, Key=os.environ['REQUEST_KEY'])['Body'].read())
              if r['request_sha256'] != correction.get('request_sha256') or rec['request_sha256'] != digest(correction):
                  raise SystemExit('the correction response does not answer the staged correction request (request_sha256 / adapter digest differ)')
              print('correction checks: OK; resolutions', len(r['dipole_acknowledgement'].get('correction_resolutions', [])), 'session_id', r['session_id'])
              print({n: (len(b), hashlib.sha256(b).hexdigest()) for n, b in raw.items()})
              with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
                  out.write(f"request_sha256={r['request_sha256']}\\n")
              raise SystemExit(0)
          r = json.loads(raw['response.json']); rec = json.loads(raw['host-session-record.json']); a = json.loads(raw['host-attestation.json'])
          for k in ('request_sha256', 'session_id', 'model_identity_as_reported_by_session', 'sections', 'feedback', 'lessons',
                    'dipole_teachback', 'dipole_observation_review', 'dipole_relationship_scan', 'dipole_novel_findings'):
              if k not in r: raise SystemExit(f'response lacks {k}')
          if len(r['sections']) != 18: raise SystemExit(f"response cites {len(r['sections'])} sections, not 18")
          if 'principal_receipt_hash' in json.dumps(r['feedback']): raise SystemExit('feedback must carry NO principal_receipt_hash')
          if not isinstance(r['lessons'], list) or not r['lessons']: raise SystemExit('response carries no lessons')
          if len(r['dipole_relationship_scan']) != 171 or len(r['dipole_observation_review']) != 19: raise SystemExit('classroom ledgers are not 19 components / 171 pairs')
"""
assert old in f; f = f.replace(old, new, 1)
old = "          def digest(value):\n              return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()\n          if rec.get('response_sha256') != digest(r): raise SystemExit('record.response_sha256 is not the adapter digest of response.json')\n"
new = "          if rec.get('response_sha256') != digest(r): raise SystemExit('record.response_sha256 is not the adapter digest of response.json')\n"
assert old in f; f = f.replace(old, new, 1)
old = "            git commit -q -m \"root: cycle $CYCLE Frankie response, attestation, host session record, analysis (uploaded from Frankie's box $INSTANCE, committed by frankie_box_fetch_response.yml run $GITHUB_RUN_ID; request_sha256 ${{ steps.files.outputs.request_sha256 }})\"\n          git push origin \"HEAD:refs/heads/$BR\"\n          git log --oneline -1; git ls-remote origin \"refs/heads/$BR\"\n          echo \"delivered $BR; next: frankie_host_record_principal_response.yml source_ref=$BR cycle_index=$CYCLE\"\n"
new = "            git commit -q -m \"root: cycle $CYCLE Frankie $TURN turn files (uploaded from Frankie's box $INSTANCE, committed by frankie_box_fetch_response.yml run $GITHUB_RUN_ID; request_sha256 ${{ steps.files.outputs.request_sha256 }})\"\n          git push origin \"HEAD:refs/heads/$BR\"\n          git log --oneline -1; git ls-remote origin \"refs/heads/$BR\"\n          echo \"delivered $BR; next: frankie_host_record_principal_response.yml source_ref=$BR cycle_index=$CYCLE turn=$TURN\"\n"
assert old in f; f = f.replace(old, new, 1)
F.write_text(f)

# ---- D. session.sh: fetch_correction and correction ----
H = Path('deploy/aws/box/frankie_box_session.sh'); h = H.read_text()
old = "# Inputs: DAY (20211003), CYCLE (00), MARKETS_REF (this branch), ACTION (start | status | preflight | verify;\n# default status; restart_session stops ONLY the session unit with a receipt to apply a session-code fix). Never stops a Pod, a box or the native host runner (Greg's word).\n"
new = "# Inputs: DAY (20211003), CYCLE (00), MARKETS_REF (this branch), ACTION (start | status | preflight | verify;\n# default status; restart_session stops ONLY the session unit with a receipt to apply a session-code fix;\n# fetch_correction takes the host's exported classroom-correction-request.json through MAP_URL into request/;\n# correction runs the session's Dipole classroom correction turn as its own unit). Never stops a Pod, a box or the native host runner (Greg's word).\n"
assert old in h; h = h.replace(old, new, 1)
old = "  echo \"--- heartbeat log tail\"; tail -n 5 \"$ROOT/logs/heartbeat-$CYCLE.log\" 2>/dev/null\n"
new = "  echo \"--- heartbeat log tail\"; tail -n 5 \"$ROOT/logs/heartbeat-$CYCLE.log\" 2>/dev/null\n  if [ -s \"$ROOT/logs/correction-$CYCLE.log\" ]; then echo \"--- correction log tail ($(systemctl is-active \"frankie-correction-$CYCLE.service\" 2>/dev/null))\"; tail -n 12 \"$ROOT/logs/correction-$CYCLE.log\"; fi\n"
assert old in h; h = h.replace(old, new, 1)
FETCH_PY = r'''import hashlib, json, os, subprocess
root = os.environ['ROOT']
m = json.load(open(os.path.join(root, 'tmp', 'presigned-map.json')))
keys = [k for k in m if k.endswith('/classroom-correction-request.json') or k == 'classroom-correction-request.json']
if len(keys) != 1: raise SystemExit(f'the map must carry exactly one classroom-correction-request.json key ({len(keys)} found)')
target = os.path.join(root, 'request', 'classroom-correction-request.json'); tmp = target + '.part'
r = subprocess.run(['curl', '-fsS', '-m', '300', '--retry', '3', '-o', tmp, m[keys[0]]['url']], capture_output=True, text=True)
if r.returncode: raise SystemExit(f'download failed: curl exit {r.returncode}')
data = open(tmp, 'rb').read()
doc = json.loads(data)
if doc.get('schema') != 'FRANKIE_DIPOLE_CLASSROOM_CORRECTION_REQUEST_V1': raise SystemExit('the downloaded file is not a Dipole classroom correction request')
if os.path.exists(target) and open(target, 'rb').read() != data:
    os.unlink(tmp); raise SystemExit('a different classroom-correction-request.json is already on the box; not overwritten (move it aside with a receipt first)')
os.replace(tmp, target)
print(f'CORRECTION_REQUEST key={keys[0]} bytes={len(data)} sha256={hashlib.sha256(data).hexdigest()} request_sha256={doc.get("request_sha256")} correction_ids={len(doc.get("correction_ids", []))} session_id={doc.get("session_id")}')
'''
old = "case \"$ACTION\" in\n  status) status ;;\n"
new = ('''fetch_correction() {
  # The host's retained classroom-correction-request.json, exported by frankie_host_export_principal_request.yml
  # (turn=correction) and presigned by frankie_box_run.yml (presign=<bucket>/<key>) into the private map at MAP_URL.
  # Fetched into request/, sha256 printed; an existing file with different bytes is never overwritten.
  [ -n "${MAP_URL:-}" ] || { echo "fetch_correction needs MAP_URL (frankie_box_run.yml presign=<bucket>/<key of classroom-correction-request.json>)"; return 2; }
  mkdir -p "$ROOT/tmp" "$ROOT/request"
  curl -fsS -m 60 --retry 3 -o "$ROOT/tmp/presigned-map.json" "$MAP_URL" || { echo "presigned map download failed"; return 2; }
  export ROOT
  "$ROOT/venv/bin/python" - <<'PY' || return 2
''' + FETCH_PY + '''PY
}
correction() {
  # The same session's turn 2 (frankie_box_boss_session.py --stage correction) as its own transient unit: one BOSS call,
  # the three correction files into out/, then the pusher with TURN=correction. Requires the fetched request and the
  # response this session wrote. Never touches the cycle session unit.
  U="frankie-correction-$CYCLE"
  if systemctl is-active --quiet "$U.service"; then echo "$U is already running"; status; return 0; fi
  [ -s "$ROOT/request/classroom-correction-request.json" ] || { echo "no correction request on the box (ACTION=fetch_correction first)"; return 2; }
  [ -s "$S/out/response.json" ] || { echo "no out/response.json: the correction belongs to the session that wrote the response"; return 2; }
  git -C "$ROOT/markets" fetch -q --depth 1 origin "$MARKETS_REF" && git -C "$ROOT/markets" checkout -q FETCH_HEAD && echo "markets HEAD $(git -C "$ROOT/markets" rev-parse HEAD)"
  systemctl reset-failed "$U.service" 2>/dev/null
  systemd-run --unit "$U" --collect -p WorkingDirectory="$S" -p StandardOutput=append:"$ROOT/logs/correction-$CYCLE.log" -p StandardError=append:"$ROOT/logs/correction-$CYCLE.log" \\
    "$ROOT/venv/bin/python" "$ROOT/markets/deploy/aws/box/frankie_box_boss_session.py" --session "$S" --day "$DAY" --cycle "$CYCLE" --stage correction >/dev/null 2>&1 \\
    && echo "$U started (the correction turn on the BOSS; minutes; watch logs/correction-$CYCLE.log)" || { echo "$U start failed"; return 3; }
  sleep 5
  status
}
case "$ACTION" in
  status) status ;;
  fetch_correction) fetch_correction ;;
  correction) correction ;;
''')
assert old in h; h = h.replace(old, new, 1)
old = "  *) echo \"ACTION must be start, status, preflight, verify or restart_session\"; exit 2 ;;"
new = "  *) echo \"ACTION must be start, status, preflight, verify, restart_session, fetch_correction or correction\"; exit 2 ;;"
assert old in h; h = h.replace(old, new, 1)
H.write_text(h)
print('export, push, fetch, session.sh edited')
