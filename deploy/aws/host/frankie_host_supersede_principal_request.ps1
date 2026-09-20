# Move one cycle's RENDERED principal request aside so it is rendered again (2026-09-20 21:55Z).
#
# Why: Greg, 2026-09-20: "we are applying this to cycle 0 and re-running cycle 0". The run-findings
# ledger now enters the prompt, so cycle 0's prompt.md and its durable session-request.json (both
# rendered before the ledger existed) must be superseded. The adapter opens prompt.md exclusively and
# compares any existing request byte for byte, so both must be out of the way; the coordinator's
# saved attachment and intent stages are superseded separately by the declared principal supersede
# (declare_identity_supersede.py --supersede-principal). MOVES, never deletes: the files go to
# <run parent>/superseded/<run name>-<stamp>-principal-cycle-NN/ with sha256 in the receipt. Refuses
# when a session-response.json exists (a recorded response is never superseded here), when a runner
# is alive, or when nothing is rendered. Leaves the request-independent files (historical-prompt.md,
# receiver/, bound-mapping.json, preparation-pins.json, adapter-config.json, sealed-proof.json,
# memory-a-witness.json, the classroom files) in place. $Day, $RunRoot, $CycleIndex, $Reason arrive
# from ssm_run_ps1.py --set; no path literal here.
$ErrorActionPreference = 'Stop'
foreach ($required in 'Day', 'RunRoot', 'CycleIndex', 'Reason') {
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
$alive = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*run_actual_sunday*' })
if ($alive.Count -gt 0) { throw ("refusing: a runner process is alive (pid " + ($alive | ForEach-Object { $_.ProcessId }) + ")") }
$principal = Join-Path (Join-Path (Join-Path $run 'execution') ('cycle-' + $CycleIndex)) 'principal'
if (-not (Test-Path $principal)) { throw ("no principal directory for cycle " + $CycleIndex + " at " + $principal) }
if (Test-Path (Join-Path $principal 'session-response.json')) { throw 'refusing: a session-response.json is recorded for this cycle; its request is never superseded' }
$names = @('prompt.md', 'session-request.json', 'run-findings-witness.json')
$names += @(Get-ChildItem -Path $principal -Directory -Filter 'response-check-*' -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
$present = @($names | Where-Object { Test-Path (Join-Path $principal $_) })
if ($present.Count -eq 0) { Write-Output 'NOTHING_RENDERED nothing to supersede'; exit 0 }
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$runName = Split-Path $run -Leaf
$target = Join-Path (Join-Path (Split-Path $run -Parent) 'superseded') ($runName + '-' + $stamp + '-principal-cycle-' + $CycleIndex)
New-Item -ItemType Directory -Path $target | Out-Null
$moved = [ordered]@{}
foreach ($name in $present) {
    $source = Join-Path $principal $name
    $item = Get-Item -LiteralPath $source
    $record = [ordered]@{ kind = $(if ($item.PSIsContainer) { 'directory' } else { 'file' }) }
    if (-not $item.PSIsContainer) { $record.bytes = $item.Length; $record.sha256 = Digest $source }
    Move-Item -LiteralPath $source -Destination (Join-Path $target $name)
    if (Test-Path -LiteralPath $source) { throw ("move left " + $name + " in place") }
    $moved[$name] = $record
    Write-Output ("MOVED " + $name + " -> " + $target)
}
$receipt = [ordered]@{
    schema          = 'FRANKIE_PRINCIPAL_REQUEST_SUPERSEDED_V1'
    day             = $Day
    run_id          = $cfg.run_id
    cycle_index     = [int]$CycleIndex
    principal       = $principal
    superseded_root = $target
    moved           = $moved
    kept            = @('historical-prompt.md', 'receiver', 'bound-mapping.json', 'preparation-pins.json', 'adapter-config.json', 'sealed-proof.json', 'memory-a-witness.json', 'dipole-classroom-*')
    reason          = $Reason
    at              = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
}
$receiptPath = Join-Path $dayDirectory ('principal-request-superseded-' + $stamp + '.json')
Set-Content -Path $receiptPath -Value ($receipt | ConvertTo-Json -Depth 5) -NoNewline -Encoding UTF8
Write-Output ("receipt: " + $receiptPath)
Write-Output ('RECEIPT ' + ($receipt | ConvertTo-Json -Depth 5 -Compress))
