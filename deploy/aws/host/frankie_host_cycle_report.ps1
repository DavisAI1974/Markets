# Read-only cycle report (2026-09-20): how one cycle ran and what Frankie found.
#
# Prints, WHOLE (Greg, 20:35Z: no limit; let him say as much as he needs to): the runner's status
# lines from day-cycles.log; the cycle coordinator's retained stages for the cycle (names, digests,
# the controller result, the completion record, the verified feedback); the lessons recorded for the
# cycle; the recorded principal response (session identity, model identity as reported, request
# attestation, Frankie's analysis entire, feedback shape); the critic outcome from the Pod (usage
# and the whole critique); the classroom status; and the cycle directory's records with mtimes.
# The SSM API keeps only about 24,000 characters of console output, so the report is ALSO written
# to a file under the day's run directory (reports/, a record beside the log, never over anything)
# and, when the workflow supplies $Url (a presigned PUT it signed and masked), uploaded there so the
# workflow can print it whole. Reads only otherwise; never opens the credential; the URL is never
# printed. $Day, $RunRoot, $ToolsRoot, $Python arrive from ssm_run_ps1.py --set; no path literal.
$ErrorActionPreference = 'Continue'
foreach ($required in 'Day', 'RunRoot', 'ToolsRoot', 'Python') {
    $value = Get-Variable -Name $required -ValueOnly -ErrorAction SilentlyContinue
    if (-not $value -or $value -like 'HOST_*') { throw "$required was not supplied by ssm_run_ps1.py --set (value: '$value')" }
}
if (-not (Get-Variable CycleIndex -ErrorAction SilentlyContinue)) { $CycleIndex = '00' }
if ($CycleIndex -notmatch '^\d{2}$') { throw "CycleIndex must be two digits (value: '$CycleIndex')" }
if (-not (Get-Variable Url -ErrorAction SilentlyContinue)) { $Url = '' }
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
report_path = Path(sys.argv[4])
class Tee:
    # every line goes to the console (the SSM API keeps about 24,000 characters of it) and to the
    # report file, which is the whole record
    def __init__(self, console, handle): self.console, self.handle = console, handle
    def write(self, text):
        self.handle.write(text)
        self.console.write(text.encode(self.console.encoding or 'utf-8', 'replace').decode(self.console.encoding or 'utf-8'))
    def flush(self): self.handle.flush(); self.console.flush()
report_path.parent.mkdir(parents=True, exist_ok=True)
if report_path.exists(): raise SystemExit(f'report file already exists, refusing to write over it: {report_path}')
report_handle = report_path.open('x', encoding='utf-8', newline='\n')
sys.stdout = Tee(sys.stdout, report_handle)
request_id = f'{run_id}-cycle-{cycle_index}'
cycle = run/'execution'/f'cycle-{cycle_index}'
def load_c15(p): return unpack(json.loads(Path(p).read_bytes()))
def stage_rows(db_path):
    db = sqlite3.connect(Path(db_path).as_uri()+'?mode=ro', uri=True)
    try: return db.execute('SELECT stage, payload, digest FROM stages WHERE request=? ORDER BY stage', (request_id,)).fetchall()
    finally: db.close()
print('### coordinator stages for', request_id)
stages = {s: (unpack(json.loads(p)), d) for s, p, d in stage_rows(run/'cycles.sqlite')} if (run/'cycles.sqlite').exists() else {}
for name, (value, digest) in stages.items(): print(f'  {name}  {digest}')
if 'controller' in stages:
    c = stages['controller'][0]
    print('### controller result')
    print(f"  status={c.get('status')} request_hash={c.get('request_hash')} keys={sorted(c.keys())}")
    for k in ('verdict', 'score', 'critique_verdict', 'critique_score', 'critic', 'evaluation', 'admission', 'native_checkpoint', 'controller_checkpoint'):
        if k in c: print(f'    {k}={json.dumps(c[k], sort_keys=True, default=str)}')
    records = c.get('records') or ()
    print(f'  records={len(records)}')
    for rec in records:
        print('    ' + json.dumps(rec, sort_keys=True, default=str))
if 'complete' in stages:
    print('### completion record'); print('  ' + json.dumps(stages['complete'][0], sort_keys=True, default=str))
if 'feedback' in stages:
    fb = stages['feedback'][0]['feedback']
    print('### verified feedback'); print(f"  available_ns={fb.get('available_ns')} input_hash={fb.get('input_hash')} sessions={len(fb.get('sessions', ()))}")
    for s in fb.get('sessions', ()):
        print(f"  session {s.get('session_id')}: timing labels={len(s.get('timing', ()))} gap={'yes' if s.get('gap') is not None else 'none'} path labels={len(s.get('path', ()))}")
if 'training' in stages:
    print('### training update'); print('  ' + json.dumps(stages['training'][0], sort_keys=True, default=str))
lessons = run/'lessons.sqlite'
if lessons.exists():
    db = sqlite3.connect(lessons.as_uri()+'?mode=ro', uri=True)
    try: rows = db.execute('SELECT request, available_ns, payload FROM lessons WHERE request=?', (request_id,)).fetchall()
    finally: db.close()
    print('### lessons recorded:', len(rows))
    for req, ns, payload in rows:
        record = unpack(json.loads(payload))
        for i, lesson in enumerate(record.get('lessons', ())):
            text = json.dumps(lesson, sort_keys=True, default=str) if not isinstance(lesson, str) else lesson
            print(f'  [{i}] ({len(text)} chars, whole)'); print(text)
response = cycle/'principal'/'session-response.json'
print('### recorded principal response:', 'present' if response.exists() else 'absent')
if response.exists():
    retained = json.loads(response.read_bytes()); r = retained.get('response', {})
    print(f"  bytes={response.stat().st_size} session_id={r.get('session_id')} model={r.get('model_identity_as_reported_by_session')}")
    print(f"  request_sha256={r.get('request_sha256')} sections cited={len(r.get('sections') or {})} host_attestation keys={sorted((retained.get('host_attestation') or {}).keys())}")
    fb = r.get('feedback') or {}
    print(f"  feedback: request_id={fb.get('request_id')} available_ns={fb.get('available_ns')} sessions={len(fb.get('sessions') or [])}")
    # Frankie's Markdown analysis is retained as its own lessons entry (ACTUAL_PRINCIPAL_RESPONSE_HANDOFF.md);
    # every entry is printed whole (the report file carries all of it; the console copy may be cut by SSM).
    entries = [json.dumps(l, sort_keys=True, default=str) if not isinstance(l, str) else l for l in (r.get('lessons') or [])]
    for i, text in enumerate(entries):
        print(f'  lesson[{i}] ({len(text)} chars, whole):'); print(text)
spool = cycle/'critic-spool'
print('### critic outcome')
if spool.exists():
    for job in sorted(spool.iterdir()):
        outcome = job/'outcome.json'
        if outcome.exists():
            o = json.loads(outcome.read_bytes())
            print(f'  job {job.name}: keys={sorted(o.keys())}')
            for k in ('status', 'phase', 'finished_at', 'output_tokens', 'incomplete', 'outcome_sha256', 'http_status', 'body_sha256'):
                if k in o: print(f'    {k}={o[k]}')
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
                        print(f"    critic usage: {json.dumps(usage, sort_keys=True)} finish_reason={choices[0].get('finish_reason')}")
                except ValueError:
                    pass
                print(f'    critic body ({len(body)} bytes decoded); content follows, whole:')
                print(text)
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
        try: print(f'  {name}: ' + json.dumps(load_c15(path), sort_keys=True, default=str))
        except Exception as error: print(f'  {name}: unreadable ({error})')
if req.exists():
    try:
        c = json.loads(req.read_bytes())
        print('  correction request keys:', sorted(c.keys()) if isinstance(c, dict) else type(c).__name__)
    except ValueError as error: print(f'  correction request unreadable ({error})')
if resp.exists():
    try:
        c = json.loads(resp.read_bytes())
        print('  correction response keys:', sorted(c.keys()) if isinstance(c, dict) else type(c).__name__)
    except ValueError as error: print(f'  correction response unreadable ({error})')
print('### cycle records (name  mtime  bytes)')
if cycle.exists():
    for p in sorted(cycle.rglob('*'), key=lambda p: p.stat().st_mtime):
        if p.is_file(): print(f"  {p.relative_to(cycle)}  {p.stat().st_mtime:.0f}  {p.stat().st_size}")
print('done (read-only; report file written whole)')
sys.stdout.flush(); sys.stdout = sys.stdout.console; report_handle.close()
'@
Set-Content -Path $probe -Value $code -Encoding ASCII
if (-not (Test-Path $Python)) { throw "host python missing: $Python" }
$env:PYTHONPATH = $ToolsRoot
$env:PYTHONIOENCODING = 'utf-8'
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$report = Join-Path (Join-Path $dayDirectory 'reports') ('cycle-' + $CycleIndex + '-report-' + $stamp + '.txt')
& $Python $probe $cfg.run_directory $CycleIndex $cfg.run_id $report
if ($LASTEXITCODE -ne 0) { throw ("report probe exited " + $LASTEXITCODE) }
if (-not (Test-Path $report)) { throw "the probe wrote no report file at $report" }
$reportBytes = (Get-Item $report).Length
$reportSha = (Get-FileHash -Path $report -Algorithm SHA256).Hash.ToLower()
Write-Output ("REPORT_FILE " + $report + " bytes=" + $reportBytes + " sha256=" + $reportSha)
if ($Url) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $previous = $ProgressPreference; $ProgressPreference = 'SilentlyContinue'
    try { Invoke-WebRequest -Uri $Url -Method Put -InFile $report -ContentType 'text/plain; charset=utf-8' -UseBasicParsing | Out-Null }
    catch {
        # name the refusal (the S3 error code and message), never the URL
        $detail = ''
        try {
            $stream = $_.Exception.Response.GetResponseStream()
            $detail = (New-Object System.IO.StreamReader($stream)).ReadToEnd()
            $detail = ($detail -replace '<RequestId>.*?</RequestId>', '') -replace '<HostId>.*?</HostId>', ''
        } catch { $detail = $_.Exception.Message }
        Write-Output ("REPORT_UPLOAD_REFUSED " + $_.Exception.Message + " " + $detail)
        throw 'the report upload was refused (the file is on the host; see REPORT_FILE)'
    }
    finally { $ProgressPreference = $previous }
    Write-Output ("REPORT_UPLOADED bytes=" + $reportBytes + " sha256=" + $reportSha)
} else { Write-Output 'REPORT_NOT_UPLOADED (no Url supplied; the console copy above may be cut by the SSM API)' }
