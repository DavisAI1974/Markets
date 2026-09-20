# Read-only cycle report (2026-09-20): how one cycle ran and what Frankie found.
#
# Prints, under the SSM output cap: the runner's status lines from day-cycles.log; the cycle
# coordinator's retained stages for the cycle (names, digests, the completion record, a summary of
# the verified feedback); the lessons recorded for the cycle (each truncated); the recorded
# principal response (session identity, model identity as reported, request attestation, lessons,
# feedback shape); the critic outcome from the Pod (summary); and the cycle directory's records
# with mtimes. Reads only; the one write is the embedded Python to $env:TEMP; never opens the
# credential. $Day, $RunRoot, $ToolsRoot, $Python arrive from ssm_run_ps1.py --set; no path literal.
$ErrorActionPreference = 'Continue'
foreach ($required in 'Day', 'RunRoot', 'ToolsRoot', 'Python') {
    $value = Get-Variable -Name $required -ValueOnly -ErrorAction SilentlyContinue
    if (-not $value -or $value -like 'HOST_*') { throw "$required was not supplied by ssm_run_ps1.py --set (value: '$value')" }
}
if (-not (Get-Variable CycleIndex -ErrorAction SilentlyContinue)) { $CycleIndex = '00' }
if ($CycleIndex -notmatch '^\d{2}$') { throw "CycleIndex must be two digits (value: '$CycleIndex')" }
$dayDirectory = Join-Path $RunRoot $Day
$cfgPath = Join-Path $dayDirectory 'actual-host-configuration.json'
if (-not (Test-Path $cfgPath)) { throw "no run configuration for $Day at $cfgPath" }
$cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
$log = Join-Path $dayDirectory 'day-cycles.log'
Write-Output "### runner status lines (last 16)"
if (Test-Path $log) {
    Select-String -Path $log -Pattern '"status": ?"' | Select-Object -Last 16 | ForEach-Object { '  ' + $_.Line.Substring(0, [Math]::Min(200, $_.Line.Length)) }
} else { Write-Output ("NO_LOG at " + $log) }
$probe = Join-Path $env:TEMP 'frankie_cycle_report.py'
$code = @'
import json, sqlite3, sys
from pathlib import Path
from research.kalshi.frankie_boss.c15_journal import unpack
run, cycle_index = Path(sys.argv[1]), sys.argv[2]
run_id = sys.argv[3]
request_id = f'{run_id}-cycle-{cycle_index}'
cycle = run/'execution'/f'cycle-{cycle_index}'
def load_c15(p): return unpack(json.loads(Path(p).read_bytes()))
def short(s, n=400):
    s = str(s).replace('\n', ' ')
    return s if len(s) <= n else s[:n] + f'... [{len(s)} chars]'
def stage_rows(db_path):
    db = sqlite3.connect(Path(db_path).as_uri()+'?mode=ro', uri=True)
    try: return db.execute('SELECT stage, payload, digest FROM stages WHERE request=? ORDER BY stage', (request_id,)).fetchall()
    finally: db.close()
print('### coordinator stages for', request_id)
stages = {s: (unpack(json.loads(p)), d) for s, p, d in stage_rows(run/'cycles.sqlite')} if (run/'cycles.sqlite').exists() else {}
for name, (value, digest) in stages.items(): print(f'  {name}  {digest[:12]}')
if 'complete' in stages:
    print('### completion record'); print('  ' + json.dumps(stages['complete'][0], sort_keys=True, default=str)[:1500])
if 'feedback' in stages:
    fb = stages['feedback'][0]['feedback']
    print('### verified feedback'); print(f"  available_ns={fb.get('available_ns')} input_hash={str(fb.get('input_hash'))[:12]} sessions={len(fb.get('sessions', ()))}")
    for s in fb.get('sessions', ())[:12]:
        print(f"  session {s.get('session_id')}: timing labels={len(s.get('timing', ()))} gap={'yes' if s.get('gap') is not None else 'none'} path labels={len(s.get('path', ()))}")
if 'training' in stages:
    print('### training update'); print('  ' + json.dumps(stages['training'][0], sort_keys=True, default=str)[:600])
lessons = run/'lessons.sqlite'
if lessons.exists():
    db = sqlite3.connect(lessons.as_uri()+'?mode=ro', uri=True)
    try: rows = db.execute('SELECT request, available_ns, payload FROM lessons WHERE request=?', (request_id,)).fetchall()
    finally: db.close()
    print('### lessons recorded:', len(rows))
    budget = 6000
    for req, ns, payload in rows:
        record = unpack(json.loads(payload))
        for i, lesson in enumerate(record.get('lessons', ())[:20]):
            text = short(json.dumps(lesson, sort_keys=True, default=str) if not isinstance(lesson, str) else lesson)
            if budget <= 0: print('  ... (output budget reached)'); break
            budget -= len(text); print(f'  [{i}] {text}')
response = cycle/'principal'/'session-response.json'
print('### recorded principal response:', 'present' if response.exists() else 'absent')
if response.exists():
    retained = json.loads(response.read_bytes()); r = retained.get('response', {})
    print(f"  bytes={response.stat().st_size} session_id={r.get('session_id')} model={r.get('model_identity_as_reported_by_session')}")
    print(f"  request_sha256={str(r.get('request_sha256'))[:16]} sections cited={len(r.get('sections') or {})} host_attestation keys={sorted((retained.get('host_attestation') or {}).keys())[:8]}")
    fb = r.get('feedback') or {}
    print(f"  feedback: request_id={fb.get('request_id')} available_ns={fb.get('available_ns')} sessions={len(fb.get('sessions') or [])}")
    # Frankie's Markdown analysis is retained as its own lessons entry (ACTUAL_PRINCIPAL_RESPONSE_HANDOFF.md);
    # print the longest entry whole (up to the SSM cap) and the others briefly.
    entries = [json.dumps(l, sort_keys=True, default=str) if not isinstance(l, str) else l for l in (r.get('lessons') or [])]
    longest = max(range(len(entries)), key=lambda i: len(entries[i])) if entries else None
    for i, text in enumerate(entries):
        if i == longest:
            print(f'  lesson[{i}] (the analysis, {len(text)} chars):'); print(text[:12000])
            if len(text) > 12000: print(f'  ... [{len(text) - 12000} more chars]')
        else:
            print(f'  lesson[{i}] {short(text, 300)}')
spool = cycle/'critic-spool'
print('### critic outcome')
if spool.exists():
    for job in sorted(spool.iterdir()):
        outcome = job/'outcome.json'
        if outcome.exists():
            o = json.loads(outcome.read_bytes())
            print(f'  job {job.name[:12]}: keys={sorted(o.keys())[:12]}')
            for k in ('status', 'phase', 'finished_at', 'output_tokens', 'incomplete', 'outcome_sha256', 'http_status', 'body_sha256'):
                if k in o: print(f'    {k}={short(o[k], 200)}')
            if isinstance(o.get('body_base64'), str):
                import base64
                try:
                    body = base64.b64decode(o['body_base64']).decode('utf-8', 'replace')
                except Exception as error:
                    body = f'<undecodable: {error}>'
                text = body
                try:
                    parsed = json.loads(body)
                    choices = parsed.get('choices') if isinstance(parsed, dict) else None
                    if choices and isinstance(choices, list):
                        message = choices[0].get('message') or {}
                        text = message.get('content') or body
                        usage = parsed.get('usage') or {}
                        print(f"    critic usage: {json.dumps(usage, sort_keys=True)[:300]} finish_reason={choices[0].get('finish_reason')}")
                except ValueError:
                    pass
                print(f'    critic body ({len(body)} bytes decoded); content follows, first 6000 chars:')
                print(text[:6000])
print('### classroom status')
classroom_files = {
    'package/source': cycle/'host-dipole-classroom-source.c15.json',
    'package/teacher-key': cycle/'host-dipole-classroom-teacher-key.c15.json',
    'package/pre-message': cycle/'host-dipole-classroom-pre-message.c15.json',
    'package/binding': cycle/'host-dipole-classroom-binding.c15.json',
    'package/adapter': cycle/'host-dipole-classroom-adapter.c15.json',
    'audit/source': cycle/'classroom-audit'/'dipole-classroom-source.json',
    'audit/teacher-key': cycle/'classroom-audit'/'dipole-classroom-teacher-key.audit.json',
    'principal/pre-message': cycle/'principal'/'dipole-classroom-pre-message.json',
    'principal/model-visible': cycle/'principal'/'dipole-classroom-model-visible.json',
    'correction/request': cycle/'principal'/'classroom-correction-request.json',
    'correction/response': cycle/'principal'/'classroom-correction-response.json',
}
for name, path in classroom_files.items():
    print(f"  {name}: {'present ' + str(path.stat().st_size) + ' bytes' if path.exists() else 'absent'}")
req, resp = classroom_files['correction/request'], classroom_files['correction/response']
print('  correction turn:', 'recorded' if resp.exists() else ('PENDING (request written, no response)' if req.exists() else 'not requested yet'))
for name in ('package/binding', 'package/adapter'):
    path = classroom_files[name]
    if path.exists():
        try: print(f'  {name}: ' + json.dumps(load_c15(path), sort_keys=True, default=str)[:900])
        except Exception as error: print(f'  {name}: unreadable ({error})')
if req.exists():
    try:
        c = json.loads(req.read_bytes())
        print('  correction request keys:', sorted(c.keys())[:12] if isinstance(c, dict) else type(c).__name__)
    except ValueError as error: print(f'  correction request unreadable ({error})')
if resp.exists():
    try:
        c = json.loads(resp.read_bytes())
        print('  correction response keys:', sorted(c.keys())[:12] if isinstance(c, dict) else type(c).__name__)
    except ValueError as error: print(f'  correction response unreadable ({error})')
print('### cycle records (name  mtime  bytes)')
if cycle.exists():
    for p in sorted(cycle.rglob('*'), key=lambda p: p.stat().st_mtime):
        if p.is_file(): print(f"  {p.relative_to(cycle)}  {p.stat().st_mtime:.0f}  {p.stat().st_size}")
print('done (read-only)')
'@
Set-Content -Path $probe -Value $code -Encoding ASCII
if (-not (Test-Path $Python)) { throw "host python missing: $Python" }
$env:PYTHONPATH = $ToolsRoot
& $Python $probe $cfg.run_directory $CycleIndex $cfg.run_id
if ($LASTEXITCODE -ne 0) { throw ("report probe exited " + $LASTEXITCODE) }
