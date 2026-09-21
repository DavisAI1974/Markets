from pathlib import Path
import os
os.chdir('/home/user/Markets')

# ---------------------------------------------------------------- the session
p = Path('deploy/aws/box/frankie_box_boss_session.py'); s = p.read_text()

# F3b: notes from worker threads under a re-entrant lock (note() is called inside _progress_note, which holds it)
old = "        self._lock = threading.Lock()\n"
new = "        self._lock = threading.RLock()     # re-entrant: note() takes it and _progress_note() calls note() while holding it\n"
assert old in s; s = s.replace(old, new, 1)
old = "    def note(self, text):\n        (self.dir / 'note').write_text(text.replace('\\n', ' ')[:400] + '\\n', encoding='utf-8')\n        print(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), text, flush=True)\n"
new = "    def note(self, text):\n        with self._lock:                        # worker threads note too (the classroom fan-out); one writer at a time\n            (self.dir / 'note').write_text(text.replace('\\n', ' ')[:400] + '\\n', encoding='utf-8')\n            print(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), text, flush=True)\n"
assert old in s, 'note'; s = s.replace(old, new, 1)
# F3a: one refusal receipt per refusal, never overwritten by a same-second twin
old = "        write_json(ROOT / 'receipts' / f'boss-session-refusal-{int(time.time())}.json',\n"
new = "        write_json(ROOT / 'receipts' / f'boss-session-refusal-{int(time.time())}-{uuid.uuid4().hex[:8]}.json',\n"
assert old in s, 'refuse'; s = s.replace(old, new, 1)
if '\nimport uuid\n' not in s:
    s = s.replace('\nimport time\n', '\nimport time\nimport uuid\n', 1)

# F2 + truncation: a classroom answer is judged by its parse, not by a reading-note length; a truncated answer is
# never kept on the correction lane and refused on turn 1 when the parser had to close a cut-off object
old = """        last = None
        for attempt in (name, name + '-retry'):
            outcome = (self.reader if lane == 'reader' else self.boss)(attempt, text)
            body = outcome.get('text') or ''
            verdict = docs.note_verdict(body, outcome)
            try:
                if verdict in ('error', 'refusal', 'empty'):
                    raise C.ClassroomOutput(f'answer unusable: {verdict}' + (f' ({outcome.get("error")})' if outcome.get('error') else ''))
                parsed = parse(body)
                if outcome.get('incomplete'):
                    self.note(f'{attempt}: output incomplete but the JSON parsed whole; kept')
                return parsed, dict(attempt=attempt, job_id=outcome.get('job_id') or outcome.get('runpod_job_id'), lane=lane,
                                    incomplete=bool(outcome.get('incomplete')), estimated_input_tokens=estimate, usage=outcome.get('usage'))
            except C.ClassroomOutput as error:
"""
new = """        last = None
        for attempt in (name, name + '-retry'):
            outcome = (self.reader if lane == 'reader' else self.boss)(attempt, text)
            body = outcome.get('text') or ''
            try:
                if outcome.get('error') and not body.strip():
                    raise C.ClassroomOutput(f'answer unusable: no output ({outcome.get("error")})')
                if body and docs.REFUSAL_RE.match(body.strip()[:300]):
                    raise C.ClassroomOutput('answer unusable: the model declined instead of answering')
                if outcome.get('incomplete') and lane == 'boss':
                    raise C.ClassroomOutput('answer unusable: output incomplete (the answer was cut off; a cut-off acknowledgement or summary is never kept)')
                parsed = parse(body)                    # a valid JSON answer is usable whatever its length (a zero-correction acknowledgement is short)
                repairs = C.parse_repairs(body)
                if outcome.get('incomplete') and any('truncat' in r or 'balanced' in r for r in repairs):
                    raise C.ClassroomOutput(f'answer unusable: output incomplete and the JSON had to be repaired ({", ".join(repairs)})')
                if outcome.get('incomplete'):
                    self.note(f'{attempt}: output incomplete but the JSON parsed whole; kept')
                return parsed, dict(attempt=attempt, job_id=outcome.get('job_id') or outcome.get('runpod_job_id'), lane=lane,
                                    incomplete=bool(outcome.get('incomplete')), repairs=repairs, estimated_input_tokens=estimate, usage=outcome.get('usage'))
            except C.ClassroomOutput as error:
"""
assert old in s, 'classroom_call'; s = s.replace(old, new, 1)

# validate() failures refuse with a receipt (never a bare traceback the re-run repeats)
old = """        summary = load_json(summary_path)
        built = C.assemble(visible, outputs, summary['parsed'])
        report = C.validate(visible, built['ledgers'])
"""
new = """        summary = load_json(summary_path)
        try:
            built = C.assemble(visible, outputs, summary['parsed'])
            report = C.validate(visible, built['ledgers'])
        except ValueError as error:
            self.refuse(f'classroom: the assembled ledgers did not validate ({str(error)[:300]}); nothing filed; the parsed answers stay under {d}')
"""
assert old in s, 'validate'; s = s.replace(old, new, 1)
old = """        C = classroom_module()
        visible = C.visible_of(self.request)
        d = self._classroom_dir()
        ledgers_path = d / 'ledgers.json'
"""
new = """        C = classroom_module()
        try:
            visible = C.visible_of(self.request)
        except ValueError as error:
            self.refuse(f'classroom: {error}')
        d = self._classroom_dir()
        ledgers_path = d / 'ledgers.json'
"""
assert old in s, 'visible'; s = s.replace(old, new, 1)

# Medium 2 + Low: the correction answer is bound to the request it answered; the request is bound to this response
old = """        correction = load_json(path)
        if correction.get('schema') != CORRECTION_REQUEST_SCHEMA or not isinstance(correction.get('correction_ids'), list):
            self.refuse(f'correction: {path} is not a Dipole classroom correction request')
"""
new = """        correction = load_json(path)
        if (correction.get('schema') != CORRECTION_REQUEST_SCHEMA or not isinstance(correction.get('correction_ids'), list)
                or any(not isinstance(correction.get(k), str) or len(correction.get(k)) != 64 for k in ('request_sha256', 'post_grade_hash', 'original_request_sha256'))):
            self.refuse(f'correction: {path} is not a complete Dipole classroom correction request (schema, correction_ids, request_sha256, post_grade_hash, original_request_sha256)')
"""
assert old in s, 'correction schema'; s = s.replace(old, new, 1)
old = """        for key in ('session_id', 'model_identity_as_reported_by_session'):
            if correction.get(key) != response.get(key):
                self.refuse(f'correction: the correction request names a different {key} than out/response.json')
"""
new = """        for key in ('session_id', 'model_identity_as_reported_by_session'):
            if correction.get(key) != response.get(key):
                self.refuse(f'correction: the correction request names a different {key} than out/response.json')
        if correction['original_request_sha256'] != response.get('request_sha256'):
            self.refuse('correction: the correction request answers a different principal request (original_request_sha256) than out/response.json answered')
"""
assert old in s, 'original'; s = s.replace(old, new, 1)
old = """        d = self._classroom_dir()
        answer_path = d / 'correction.json'
        if not answer_path.exists():
"""
new = """        d = self._classroom_dir()
        answer_path = d / f'correction-{correction["request_sha256"][:16]}.json'      # one answer per correction request, never reused across requests
        if answer_path.exists():
            bound = load_json(answer_path).get('correction_request') or {}
            if bound.get('request_sha256') != correction['request_sha256'] or bound.get('post_grade_hash') != correction['post_grade_hash']:
                self.refuse(f'correction: {answer_path.name} answers another correction request ({bound.get("request_sha256", "")[:16]} / {bound.get("post_grade_hash", "")[:16]}); move it aside with a receipt')
        if not answer_path.exists():
"""
assert old in s, 'cache'; s = s.replace(old, new, 1)

# the receipts packet: the writing calls that follow it are excluded by construction, so the writing gate is stable
old = "        report = receipts_module().write(self.work, READING_LEDGER)\n"
new = "        report = receipts_module().write(self.work, READING_LEDGER, exclude_prefixes=('write-',))   # the writing calls follow this packet; listing them here would move the writing gate on every restart\n"
assert old in s, 'receipts write'; s = s.replace(old, new, 1)
p.write_text(s)

# ---------------------------------------------------------------- the classroom module
c = Path('deploy/aws/box/frankie_box_classroom.py'); t = c.read_text()
old = """def tolerant_json(text):
    \"\"\"frankie_box_docs.tolerant_json (fences, first balanced object, comments, trailing commas, truncated close).\"\"\"
    path = Path(__file__).resolve().parent / 'frankie_box_docs.py'
    spec = importlib.util.spec_from_file_location('frankie_box_docs_for_classroom', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.tolerant_json(text)
"""
new = """def tolerant_json(text):
    \"\"\"frankie_box_docs.tolerant_json (fences, first balanced object, comments, trailing commas, truncated close).\"\"\"
    path = Path(__file__).resolve().parent / 'frankie_box_docs.py'
    spec = importlib.util.spec_from_file_location('frankie_box_docs_for_classroom', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.tolerant_json(text)


def parse_repairs(text):
    \"\"\"The repairs the tolerant parser applied to this text (empty when it parsed as written).\"\"\"
    _, repairs = tolerant_json(text or '')
    return list(repairs or [])
"""
assert old in t, 'tolerant'; t = t.replace(old, new, 1)
# parse_correction: a duplicate correction_id is a refusal, not a silent last-wins
old = """        if item['correction_id'] not in ids:
            raise ClassroomOutput(f'unknown correction_id {item["correction_id"]!r}')
        by_id[item['correction_id']] = _text(item.get('corrected_understanding'), f'corrected_understanding for {item["correction_id"]}')
"""
new = """        if item['correction_id'] not in ids:
            raise ClassroomOutput(f'unknown correction_id {item["correction_id"]!r}')
        if item['correction_id'] in by_id:
            raise ClassroomOutput(f'duplicate correction_id {item["correction_id"]!r}')
        by_id[item['correction_id']] = _text(item.get('corrected_understanding'), f'corrected_understanding for {item["correction_id"]}')
"""
assert old in t, 'dup'; t = t.replace(old, new, 1)
# Markdown: model text never breaks the table or opens a fence
old = "# ---- the human-readable record ----------------------------------------------------------------------------------------\ndef render_markdown(ledgers, dropped_findings=()):\n"
new = """# ---- the human-readable record ----------------------------------------------------------------------------------------
def _cell(text):
    \"\"\"Model text inside a Markdown table cell or heading: one line, pipes escaped, no fence can open.\"\"\"
    return str(text).replace('\\r', ' ').replace('\\n', ' ').replace('|', '\\\\|').replace('```', "'''")


def render_markdown(ledgers, dropped_findings=()):
"""
assert old in t, 'render head'; t = t.replace(old, new, 1)
old = "        lines += [f'### {c[\"name\"]}', '', f'state_counts {json.dumps(c[\"state_counts\"], sort_keys=True)}; terminal {c[\"terminal_state\"]}; direction {c[\"direction\"]}', '']\n        for field in NARRATIVE:\n            lines.append(f'- {field}: {c[field]}')\n"
new = "        lines += [f'### {c[\"name\"]}', '', f'state_counts {json.dumps(c[\"state_counts\"], sort_keys=True)}; terminal {c[\"terminal_state\"]}; direction {c[\"direction\"]}', '']\n        for field in NARRATIVE:\n            lines.append(f'- {field}: {_cell(c[field])}')\n"
assert old in t, 'narr'; t = t.replace(old, new, 1)
old = "        lines.append(f'| {p[\"left\"]} | {p[\"right\"]} | {p[\"direction_relation\"]} | {p[\"developing_structure\"] or \"\"} | {p[\"correlation_interpretation\"]} |')\n"
new = "        lines.append(f'| {p[\"left\"]} | {p[\"right\"]} | {p[\"direction_relation\"]} | {_cell(p[\"developing_structure\"] or \"\")} | {_cell(p[\"correlation_interpretation\"])} |')\n"
assert old in t, 'scan row'; t = t.replace(old, new, 1)
old = "        lines += [f'### {f[\"finding_id\"]}', '', f'Premise: {f[\"premise\"]}', '', f'Why novel: {f[\"why_novel\"]}', '', 'Evidence references:']\n"
new = "        lines += [f'### {_cell(f[\"finding_id\"])}', '', f'Premise: {_cell(f[\"premise\"])}', '', f'Why novel: {_cell(f[\"why_novel\"])}', '', 'Evidence references:']\n"
assert old in t, 'finding'; t = t.replace(old, new, 1)
old = "            lines += [f'- {d.get(\"finding_id\")}: {d[\"reason\"]}', f'  `{json.dumps(d.get(\"raw\"), sort_keys=True)[:2000]}`']\n"
new = "            lines += [f'- {_cell(d.get(\"finding_id\"))}: {_cell(d[\"reason\"])}', f'  `{json.dumps(d.get(\"raw\"), sort_keys=True)[:2000].replace(chr(96), chr(39))}`']\n"
assert old in t, 'dropped'; t = t.replace(old, new, 1)
c.write_text(t)

# ---------------------------------------------------------------- the receipts packet
r = Path('deploy/aws/box/frankie_box_receipts.py'); u = r.read_text()
old = """def provider_invocations(work):
    \"\"\"Every model call the session made, from the durable job directories: the BOSS (Pod, jobs_v1) and the reading lane
    (RunPod serverless), each with its request witness, result witness, usage and model as the provider reported them.\"\"\"
    work = Path(work)
    out = []
"""
new = """def provider_invocations(work, exclude_prefixes=()):
    \"\"\"Every model call the session made, from the durable job directories: the BOSS (Pod, jobs_v1) and the reading lane
    (RunPod serverless), each with its request witness, result witness, usage and model as the provider reported them.
    exclude_prefixes: job names left out by construction (the writing calls, whose prompts carry this packet: listing
    them would move the packet, and the writing gate with it, on every restart).\"\"\"
    work = Path(work)
    out = []
"""
assert old in u, 'inv'; u = u.replace(old, new, 1)
old = """            request, outcome = _load(d / 'request.json') or {}, _load(d / 'outcome.json') or {}
            item = dict(lane=lane, name=request.get('name') or outcome.get('name') or d.name, job_directory=d.name,
"""
new = """            request, outcome = _load(d / 'request.json') or {}, _load(d / 'outcome.json') or {}
            job_name = request.get('name') or outcome.get('name') or d.name
            if any(str(job_name).startswith(prefix) for prefix in exclude_prefixes):
                continue
            item = dict(lane=lane, name=job_name, job_directory=d.name,
"""
assert old in u, 'inv2'; u = u.replace(old, new, 1)
old = "def build(work, reading_ledger=None):\n    return dict(schema=SCHEMA, at=time.time(), provider_invocations=provider_invocations(work), knowledge_retrieval=knowledge_retrieval(work, reading_ledger),\n                answer_wall=answer_wall(work))\n"
new = "def build(work, reading_ledger=None, exclude_prefixes=()):\n    return dict(schema=SCHEMA, at=time.time(), provider_invocations=provider_invocations(work, exclude_prefixes), excluded_prefixes=list(exclude_prefixes),\n                knowledge_retrieval=knowledge_retrieval(work, reading_ledger), answer_wall=answer_wall(work))\n"
assert old in u, 'build'; u = u.replace(old, new, 1)
old = "def write(work, reading_ledger=None):\n    work = Path(work)\n    report = build(work, reading_ledger)\n"
new = "def write(work, reading_ledger=None, exclude_prefixes=()):\n    work = Path(work)\n    report = build(work, reading_ledger, exclude_prefixes)\n"
assert old in u, 'write'; u = u.replace(old, new, 1)
old = "             f'## Provider invocations ({len(p)}: {sum(1 for i in p if i[\"lane\"] == \"boss\")} BOSS jobs on the Pod, {sum(1 for i in p if i[\"lane\"] == \"serverless\")} serverless jobs)', '',\n"
new = "             f'## Provider invocations ({len(p)}: {sum(1 for i in p if i[\"lane\"] == \"boss\")} BOSS jobs on the Pod, {sum(1 for i in p if i[\"lane\"] == \"serverless\")} serverless jobs'\n             + (f'; the calls named {\", \".join(report.get(\"excluded_prefixes\", []))}* follow this packet and are not in it by construction)' if report.get('excluded_prefixes') else ')'), '',\n"
assert old in u, 'render'; u = u.replace(old, new, 1)
r.write_text(u)

# ---------------------------------------------------------------- the box shell: fetch_correction binds and cleans up
h = Path('deploy/aws/box/frankie_box_session.sh'); v = h.read_text()
old = """data = open(tmp, 'rb').read()
doc = json.loads(data)
if doc.get('schema') != 'FRANKIE_DIPOLE_CLASSROOM_CORRECTION_REQUEST_V1': raise SystemExit('the downloaded file is not a Dipole classroom correction request')
"""
new = """data = open(tmp, 'rb').read()
if 'bytes' in m[keys[0]] and int(m[keys[0]]['bytes']) != len(data): os.unlink(tmp); raise SystemExit(f'downloaded {len(data)} bytes, the map says {m[keys[0]]["bytes"]}')
doc = json.loads(data)
if doc.get('schema') != 'FRANKIE_DIPOLE_CLASSROOM_CORRECTION_REQUEST_V1': os.unlink(tmp); raise SystemExit('the downloaded file is not a Dipole classroom correction request')
response_path = os.path.join(root, 'session', 'out', 'response.json')
if os.path.exists(response_path):
    answered = json.load(open(response_path, 'rb')).get('request_sha256')
    if doc.get('original_request_sha256') != answered:
        os.unlink(tmp); raise SystemExit(f'the correction request answers principal request {str(doc.get("original_request_sha256"))[:16]}, this box answered {str(answered)[:16]}; not taken')
"""
assert old in v, 'fetch bind'; v = v.replace(old, new, 1)
old = """  curl -fsS -m 60 --retry 3 -o "$ROOT/tmp/presigned-map.json" "$MAP_URL" || { echo "presigned map download failed"; return 2; }
  export ROOT
  "$ROOT/venv/bin/python" - <<'PY' || return 2
"""
new = """  curl -fsS -m 60 --retry 3 -o "$ROOT/tmp/presigned-map.json" "$MAP_URL" || { echo "presigned map download failed"; return 2; }
  export ROOT
  trap 'rm -f "$ROOT/tmp/presigned-map.json"' RETURN      # the presigned URLs do not stay on the disk
  "$ROOT/venv/bin/python" - <<'PY' || return 2
"""
assert old in v, 'trap'; v = v.replace(old, new, 1)
old = "  git -C \"$ROOT/markets\" fetch -q --depth 1 origin \"$MARKETS_REF\" && git -C \"$ROOT/markets\" checkout -q FETCH_HEAD && echo \"markets HEAD $(git -C \"$ROOT/markets\" rev-parse HEAD)\"\n  systemctl reset-failed \"$U.service\" 2>/dev/null\n"
new = "  git -C \"$ROOT/markets\" fetch -q --depth 1 origin -- \"$MARKETS_REF\" && git -C \"$ROOT/markets\" checkout -q FETCH_HEAD && echo \"markets HEAD $(git -C \"$ROOT/markets\" rev-parse HEAD)\"\n  systemctl reset-failed \"$U.service\" 2>/dev/null\n"
assert old in v, 'git --'; v = v.replace(old, new, 1)
h.write_text(v)
push = Path('deploy/aws/box/frankie_box_push_response.sh'); w = push.read_text()
old = "  curl -fsS -m 60 --retry 3 -o \"$T/response-upload-map.json\" \"$MAP_URL\" || { echo \"upload map download failed\"; exit 2; }\n  export T\n"
new = "  curl -fsS -m 60 --retry 3 -o \"$T/response-upload-map.json\" \"$MAP_URL\" || { echo \"upload map download failed\"; exit 2; }\n  export T\n  trap 'rm -f \"$T/response-upload-map.json\"' EXIT      # the presigned URLs do not stay on the disk\n"
assert old in w, 'push trap'; w = w.replace(old, new, 1)
push.write_text(w)

# ---------------------------------------------------------------- the host supersede: the gate never fails open; planned receipt; runner match by command line
ps = Path('deploy/aws/host/frankie_host_supersede_principal_response.ps1'); x = ps.read_text()
old = "foreach ($required in 'Day', 'RunRoot', 'CycleIndex', 'Reason') {\n"
new = "foreach ($required in 'Day', 'RunRoot', 'CycleIndex', 'Reason', 'Python') {\n"
assert old in x, 'ps req'; x = x.replace(old, new, 1)
old = "$alive = @(Get-CimInstance Win32_Process -Filter \"Name = 'python.exe'\" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*run_actual_sunday*' })\n"
new = "$alive = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*run_actual_sunday*' })\n"
assert old in x, 'alive'; x = x.replace(old, new, 1)
old = """$cyclesDb = Join-Path $run 'cycles.sqlite'
if (Test-Path $cyclesDb) {
    $sqlite = Get-Command sqlite3 -ErrorAction SilentlyContinue
    if ($sqlite) {
        $accepted = & $sqlite.Source $cyclesDb "select count(*) from stages where stage='principal_output' and request like '%cycle-$CycleIndex%';" 2>$null
        if ($accepted -and [int]$accepted -gt 0) { throw 'refusing: the coordinator retains a principal_output for this request (the runner accepted the response); not superseded here' }
    } else { Write-Output 'NOTE sqlite3 not on PATH: the principal_output gate is not checked here (the runner refuses a superseded response it already accepted)' }
}
"""
new = """$cyclesDb = Join-Path $run 'cycles.sqlite'
$gate = 'no cycles.sqlite'
if (Test-Path $cyclesDb) {
    if (-not (Test-Path $Python)) { throw ("host python missing: " + $Python) }
    # Read-only through the host interpreter's sqlite3 (uri mode=ro: no -wal/-shm side files); any error is a refusal, never a pass.
    $gateCode = "import sqlite3,sys`nc=sqlite3.connect('file:'+sys.argv[1].replace('\\\\','/')+'?mode=ro',uri=True)`nprint(c.execute(\\"select count(*) from stages where stage='principal_output' and request like ?\\",('%cycle-'+sys.argv[2]+'%',)).fetchone()[0])"
    $accepted = (& $Python -c $gateCode $cyclesDb $CycleIndex 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $accepted -notmatch '^\\d+$') { throw ('refusing: the principal_output gate could not be evaluated (' + $accepted + ')') }
    if ([int]$accepted -gt 0) { throw 'refusing: the coordinator retains a principal_output for this request (the runner accepted the response); not superseded here' }
    $gate = 'checked: 0 principal_output stages for this request'
}
"""
assert old in x, 'gate'; x = x.replace(old, new, 1)
old = """New-Item -ItemType Directory -Path (Join-Path $target 'principal') | Out-Null
$moved = [ordered]@{}
"""
new = """New-Item -ItemType Directory -Path (Join-Path $target 'principal') | Out-Null
# The plan is receipted BEFORE the first move, so a move that fails midway leaves a record of what was to move where.
$plannedPath = Join-Path $dayDirectory ('principal-response-supersede-planned-' + $stamp + '.json')
Set-Content -Path $plannedPath -Value ([ordered]@{ schema = 'FRANKIE_PRINCIPAL_RESPONSE_SUPERSEDE_PLANNED_V1'; cycle_index = [int]$CycleIndex; principal = $principal; superseded_root = $target; planned = $present; principal_output_gate = $gate; at = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() } | ConvertTo-Json -Depth 4) -NoNewline -Encoding UTF8
Write-Output ("planned: " + $plannedPath)
$moved = [ordered]@{}
"""
assert old in x, 'planned'; x = x.replace(old, new, 1)
old = "    moved           = $moved\n    kept            = @('session-request.json'"
new = "    moved           = $moved\n    principal_output_gate = $gate\n    planned_receipt = $plannedPath\n    kept            = @('session-request.json'"
assert old in x, 'receipt'; x = x.replace(old, new, 1)
ps.write_text(x)
wf = Path('.github/workflows/frankie_host_supersede_principal_response.yml'); y = wf.read_text()
old = "      run_root:\n        description: 'Day pipeline RunRoot on the host'\n        required: false\n        default: 'C:/Codex/Frankie-BOSS-20260919/days'\npermissions:\n  contents: read\njobs:\n"
new = "      run_root:\n        description: 'Day pipeline RunRoot on the host'\n        required: false\n        default: 'C:/Codex/Frankie-BOSS-20260919/days'\n      python:\n        description: 'Host actual-run interpreter (reads cycles.sqlite read-only for the principal_output gate)'\n        required: false\n        default: 'C:/Codex/Frankie-BOSS-20260919/actual-host-python/Scripts/python.exe'\npermissions:\n  contents: read\nconcurrency:\n  group: host-${{ inputs.instance }}\n  cancel-in-progress: false\njobs:\n"
assert old in y, 'wf inputs'; y = y.replace(old, new, 1)
old = "          [[ \"$DAY\" =~ ^[0-9]{8}$ ]] || { echo \"day must be YYYYMMDD\"; exit 1; }\n"
new = "          [[ \"$DAY\" =~ ^[0-9]{8}$ ]] || { echo \"day must be YYYYMMDD\"; exit 1; }\n          [[ \"$INSTANCE\" =~ ^i-[0-9a-f]{8,17}$ ]] || { echo \"instance must be an EC2 instance id\"; exit 1; }\n"
assert old in y, 'wf validate'; y = y.replace(old, new, 1)
old = "        env:\n          CYCLE_INDEX: ${{ inputs.cycle_index }}\n          REASON: ${{ inputs.reason }}\n          DAY: ${{ inputs.day }}\n        run: |\n"
new = "        env:\n          CYCLE_INDEX: ${{ inputs.cycle_index }}\n          REASON: ${{ inputs.reason }}\n          DAY: ${{ inputs.day }}\n          INSTANCE: ${{ inputs.instance }}\n        run: |\n"
assert old in y, 'wf env'; y = y.replace(old, new, 1)
old = "          CYCLE_INDEX: ${{ inputs.cycle_index }}\n          REASON: ${{ inputs.reason }}\n        run: |\n          python deploy/aws/ssm_run_ps1.py \\\n"
new = "          CYCLE_INDEX: ${{ inputs.cycle_index }}\n          REASON: ${{ inputs.reason }}\n          HOST_PYTHON: ${{ inputs.python }}\n        run: |\n          python deploy/aws/ssm_run_ps1.py \\\n"
assert old in y, 'wf py env'; y = y.replace(old, new, 1)
old = "            --set \"Reason=$REASON\" \\\n            --timeout 600 --tail 0 --comment \"supersede the cycle $CYCLE_INDEX recorded principal response for day $DAY\"\n"
new = "            --set \"Reason=$REASON\" \\\n            --set \"Python=$HOST_PYTHON\" \\\n            --timeout 600 --tail 0 --comment \"supersede the cycle $CYCLE_INDEX recorded principal response for day $DAY\"\n"
assert old in y, 'wf set'; y = y.replace(old, new, 1)
wf.write_text(y)
print('ship fixes applied')
