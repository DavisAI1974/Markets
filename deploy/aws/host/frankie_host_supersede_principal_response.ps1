# Move one cycle's RECORDED principal response aside so a corrected response to the SAME request can be recorded
# (2026-09-21, the Dipole classroom exchange; Greg: option 1).
#
# Why: cycle 0's response was recorded (run 35633661236) and the runner stopped on it inside the classroom grade
# (no dipole_teachback). The request is unchanged (same request_sha256), so nothing is re-rendered: only the recorded
# response and what the recorder placed beside it are moved aside, and the box's corrected response answers the same
# request. MOVES, never deletes: session-response.json, host-session-record.json, every incoming-*/ and
# response-check-*/ directory, and any classroom turn files the runner had written for that response
# (classroom-correction-request.json, classroom-correction-response.json, host-correction-record.json,
# dipole-classroom-teachback.json, dipole-classroom-novel-findings.json, dipole-classroom-novelty-investigation.json,
# dipole-classroom-acknowledgement.json, dipole-classroom-completion.json, dipole-classroom-transcript.md,
# dipole-classroom-receipt.json) plus the audit directory's post-grade, go to
# <run parent>/superseded/<run name>-<stamp>-principal-response-cycle-NN/ with sha256 in the receipt. Refuses when a
# runner is alive, when the cycle holds a classroom completion (a finished classroom is never superseded here), when the
# coordinator retains a principal_output for the request (the runner accepted the response), or when nothing is
# recorded. Leaves the request and everything request-independent in place. $Day, $RunRoot, $CycleIndex, $Reason
# arrive from ssm_run_ps1.py --set; no path literal here.
$ErrorActionPreference = 'Stop'
foreach ($required in 'Day', 'RunRoot', 'CycleIndex', 'Reason', 'Python') {
    $value = Get-Variable -Name $required -ValueOnly -ErrorAction SilentlyContinue
    if (-not $value -or $value -like 'HOST_*') { throw "$required was not supplied by ssm_run_ps1.py --set (value: '$value')" }
}
if ($CycleIndex -notmatch '^\d{2}$') { throw "CycleIndex must be two digits (value: '$CycleIndex')" }
$dayDirectory = Join-Path $RunRoot $Day
$cfgPath = Join-Path $dayDirectory 'actual-host-configuration.json'
if (-not (Test-Path $cfgPath)) { throw "no run configuration for $Day at $cfgPath" }
$cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
$sha = [System.Security.Cryptography.SHA256]::Create()
function Digest([string]$path) { ([BitConverter]::ToString($script:sha.ComputeHash([IO.File]::ReadAllBytes($path)))).Replace('-', '').ToLower() }
$run = $cfg.run_directory
if (-not $run -or -not (Test-Path $run)) { throw ("run directory absent: " + $run) }
$alive = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*run_actual_sunday*' })
if ($alive.Count -gt 0) { throw ("refusing: a runner process is alive (pid " + ($alive | ForEach-Object { $_.ProcessId }) + ")") }
$cycle = Join-Path (Join-Path $run 'execution') ('cycle-' + $CycleIndex)
$principal = Join-Path $cycle 'principal'
$audit = Join-Path $cycle 'classroom-audit'
if (-not (Test-Path $principal)) { throw ("no principal directory for cycle " + $CycleIndex + " at " + $principal) }
if (Test-Path (Join-Path $principal 'dipole-classroom-completion.json')) { throw 'refusing: this cycle holds a Dipole classroom completion; a finished classroom is never superseded here' }
# The coordinator's stages live in cycles.sqlite beside the run (stage = principal_output means the runner ACCEPTED the
# response). Read only, through the host python's sqlite3 in uri mode=ro; a gate that cannot be evaluated REFUSES
# (never passes silently), and the runner itself refuses a superseded response it already accepted.
$cyclesDb = Join-Path $run 'cycles.sqlite'
$gate = 'no cycles.sqlite'
if (Test-Path $cyclesDb) {
    if (-not (Test-Path $Python)) { throw ("host python missing: " + $Python) }
    # Read-only through the host interpreter's sqlite3 (uri mode=ro: no -wal/-shm side files); any error is a refusal, never a pass.
    $gateCode = "import sqlite3,sys`nc=sqlite3.connect('file:'+sys.argv[1].replace('\\','/')+'?mode=ro',uri=True)`nprint(c.execute(\"select count(*) from stages where stage='principal_output' and request like ?\",('%cycle-'+sys.argv[2]+'%',)).fetchone()[0])"
    $accepted = (& $Python -c $gateCode $cyclesDb $CycleIndex 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $accepted -notmatch '^\d+$') { throw ('refusing: the principal_output gate could not be evaluated (' + $accepted + ')') }
    if ([int]$accepted -gt 0) { throw 'refusing: the coordinator retains a principal_output for this request (the runner accepted the response); not superseded here' }
    $gate = 'checked: 0 principal_output stages for this request'
}
$names = @('session-response.json', 'host-session-record.json', 'classroom-correction-request.json', 'classroom-correction-response.json',
           'host-correction-record.json', 'dipole-classroom-teachback.json', 'dipole-classroom-novel-findings.json',
           'dipole-classroom-novelty-investigation.json', 'dipole-classroom-acknowledgement.json', 'dipole-classroom-completion.json',
           'dipole-classroom-transcript.md', 'dipole-classroom-receipt.json')
$names += @(Get-ChildItem -Path $principal -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'incoming-*' -or $_.Name -like 'response-check-*' } | ForEach-Object { $_.Name })
$present = @($names | Where-Object { Test-Path (Join-Path $principal $_) })
if (-not (Test-Path (Join-Path $principal 'session-response.json'))) { Write-Output 'NOTHING_RECORDED no session-response.json for this cycle; nothing to supersede'; exit 0 }
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$runName = Split-Path $run -Leaf
$target = Join-Path (Join-Path (Split-Path $run -Parent) 'superseded') ($runName + '-' + $stamp + '-principal-response-cycle-' + $CycleIndex)
New-Item -ItemType Directory -Path (Join-Path $target 'principal') | Out-Null
# The plan is receipted BEFORE the first move, so a move that fails midway leaves a record of what was to move where.
$plannedPath = Join-Path $dayDirectory ('principal-response-supersede-planned-' + $stamp + '.json')
Set-Content -Path $plannedPath -Value ([ordered]@{ schema = 'FRANKIE_PRINCIPAL_RESPONSE_SUPERSEDE_PLANNED_V1'; cycle_index = [int]$CycleIndex; principal = $principal; superseded_root = $target; planned = $present; principal_output_gate = $gate; at = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() } | ConvertTo-Json -Depth 4) -NoNewline -Encoding UTF8
Write-Output ("planned: " + $plannedPath)
$moved = [ordered]@{}
foreach ($name in $present) {
    $source = Join-Path $principal $name
    $item = Get-Item -LiteralPath $source
    $record = [ordered]@{ kind = $(if ($item.PSIsContainer) { 'directory' } else { 'file' }) }
    if (-not $item.PSIsContainer) { $record.bytes = $item.Length; $record.sha256 = Digest $source }
    Move-Item -LiteralPath $source -Destination (Join-Path (Join-Path $target 'principal') $name)
    if (Test-Path -LiteralPath $source) { throw ("move left " + $name + " in place") }
    $moved['principal/' + $name] = $record
    Write-Output ("MOVED principal/" + $name + " -> " + $target)
}
$grade = Join-Path $audit 'dipole-classroom-post-grade.json'
if (Test-Path $grade) {
    New-Item -ItemType Directory -Path (Join-Path $target 'classroom-audit') | Out-Null
    $record = [ordered]@{ kind = 'file'; bytes = (Get-Item $grade).Length; sha256 = Digest $grade }
    Move-Item -LiteralPath $grade -Destination (Join-Path (Join-Path $target 'classroom-audit') 'dipole-classroom-post-grade.json')
    if (Test-Path -LiteralPath $grade) { throw 'move left the post-grade in place' }
    $moved['classroom-audit/dipole-classroom-post-grade.json'] = $record
    Write-Output ("MOVED classroom-audit/dipole-classroom-post-grade.json -> " + $target)
}
$receipt = [ordered]@{
    schema          = 'FRANKIE_PRINCIPAL_RESPONSE_SUPERSEDED_V1'
    day             = $Day
    run_id          = $cfg.run_id
    cycle_index     = [int]$CycleIndex
    principal       = $principal
    superseded_root = $target
    moved           = $moved
    principal_output_gate = $gate
    planned_receipt = $plannedPath
    kept            = @('session-request.json', 'prompt.md', 'historical-prompt.md', 'receiver', 'bound-mapping.json', 'preparation-pins.json', 'adapter-config.json', 'sealed-proof.json', 'memory-a-witness.json', 'run-findings-witness.json', 'calculation-pin-witness.json', 'dipole-classroom-pre-message.json', 'dipole-classroom-model-visible.json', 'classroom-audit/dipole-classroom-source.json', 'classroom-audit/dipole-classroom-teacher-key.audit.json')
    reason          = $Reason
    at              = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
}
$receiptPath = Join-Path $dayDirectory ('principal-response-superseded-' + $stamp + '.json')
Set-Content -Path $receiptPath -Value ($receipt | ConvertTo-Json -Depth 5) -NoNewline -Encoding UTF8
Write-Output ("receipt: " + $receiptPath)
Write-Output ('RECEIPT ' + ($receipt | ConvertTo-Json -Depth 5 -Compress))
