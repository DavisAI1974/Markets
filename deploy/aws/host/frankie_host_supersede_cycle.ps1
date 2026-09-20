# Move one OPEN cycle's retained state aside so the cycle runs again FROM THE BEGINNING (2026-09-20 22:20Z).
#
# Why: Greg, 2026-09-20: "It feels like we are skipping steps doing things this way which is why i wanted
# a full rerun from the beginning and not steps." A cycle whose Frankie half never ran is re-run whole:
# native BOSS, Granite critic, export, Frankie's request with the classroom, learning, in the designed
# order, under the current code. This script moves the cycle's whole execution directory
# (execution/cycle-NN: controller and native journals and witnesses, the request plan, the critic request,
# the readiness, the principal directory with its rendered request and the classroom artifacts, the
# classroom audit) and the coordinator's handoff export directory (handoff-<sha256(request id)>) into
# <run parent>/superseded/<run name>-<stamp>-cycle-NN/ with sha256 per file in the receipt. The
# coordinator's saved stages are superseded separately by the declared cycle supersede
# (declare_identity_supersede.py --supersede-cycle). MOVES, never deletes. Refuses when a
# session-response.json is recorded for the cycle (a recorded Frankie response is never superseded here),
# when a runner is alive, or when nothing is retained. $Day, $RunRoot, $CycleIndex, $Reason arrive from
# ssm_run_ps1.py --set; no path literal here.
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
$requestId = $cfg.run_id + '-cycle-' + $CycleIndex
$requestSha = ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($requestId)))).Replace('-', '').ToLower()
$cycle = Join-Path (Join-Path $run 'execution') ('cycle-' + $CycleIndex)
$handoff = Join-Path $run ('handoff-' + $requestSha)
if (Test-Path (Join-Path (Join-Path $cycle 'principal') 'session-response.json')) { throw 'refusing: a session-response.json is recorded for this cycle; the cycle is never superseded' }
$candidates = @(@{ name = ('execution/cycle-' + $CycleIndex); path = $cycle }, @{ name = ('handoff-' + $requestSha); path = $handoff })
$present = @($candidates | Where-Object { Test-Path $_.path })
if ($present.Count -eq 0) { Write-Output 'NOTHING_RETAINED nothing to supersede'; exit 0 }
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$runName = Split-Path $run -Leaf
$target = Join-Path (Join-Path (Split-Path $run -Parent) 'superseded') ($runName + '-' + $stamp + '-cycle-' + $CycleIndex)
New-Item -ItemType Directory -Path $target | Out-Null
$moved = [ordered]@{}
foreach ($entry in $present) {
    $source = $entry.path
    $files = [ordered]@{}
    foreach ($file in @(Get-ChildItem -LiteralPath $source -Recurse -File)) {
        $relative = $file.FullName.Substring($source.Length).TrimStart('\', '/').Replace('\', '/')
        $files[$relative] = [ordered]@{ bytes = $file.Length; sha256 = (Digest $file.FullName) }
    }
    $destination = Join-Path $target ($entry.name.Replace('/', '__'))
    Move-Item -LiteralPath $source -Destination $destination
    if (Test-Path -LiteralPath $source) { throw ("move left " + $entry.name + " in place") }
    $moved[$entry.name] = [ordered]@{ destination = $destination; files = $files }
    Write-Output ("MOVED " + $entry.name + " (" + $files.Count + " files) -> " + $destination)
}
$receipt = [ordered]@{
    schema          = 'FRANKIE_CYCLE_STATE_SUPERSEDED_V1'
    day             = $Day
    run_id          = $cfg.run_id
    request_id      = $requestId
    cycle_index     = [int]$CycleIndex
    superseded_root = $target
    moved           = $moved
    kept            = @('cycles.sqlite (stages superseded by the declared cycle supersede)', 'lessons.sqlite', 'host-instance.c15.json', 'native-host-runtime.json', 'verified-*', 'host-prefix')
    reason          = $Reason
    at              = [int][double]::Parse((Get-Date -UFormat %s))
}
$receiptPath = Join-Path $dayDirectory ('cycle-state-superseded-' + $stamp + '.json')
[IO.File]::WriteAllText($receiptPath, ($receipt | ConvertTo-Json -Depth 8))
Write-Output ('receipt: ' + $receiptPath)
Write-Output ('RECEIPT ' + ($receipt | ConvertTo-Json -Depth 8 -Compress))
