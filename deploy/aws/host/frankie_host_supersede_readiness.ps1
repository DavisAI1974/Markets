# Supersede the delivered readiness of one cycle request so a re-pinned readiness can be delivered
# (2026-09-20). Read frankie_host_cycle_binding_probe.ps1 section 7 and CLAUDE_HANDOFF_20260920.md.
#
# Why: the readiness delivered at 11:28Z (run 35507896975) pins request 6cd46f98..., the request the
# host prepared while its checkout carried CRLF sources. After the line-ending normalization the
# host prepares request a7b72cf9... (the LF request the observer world has always used; its archive
# is on the branch), and run_actual_sunday.py:833 refuses 'startup admission differs from the actual
# prepared request'. A fresh readiness bound to a7b72cf9... must be delivered, and the delivery
# refuses while the trigger exists (immutable by design). The runner also re-reads
# cycle-NN/host-service.c15.json, which pins the OLD readiness directory and pins sha, so it moves too.
#
# NOTHING IS DELETED. The trigger directory of the request, the readiness directory of the request
# and the cycle's host-service.c15.json are MOVED into <RunRoot parent>/superseded/readiness-<stamp>/
# with sha256 recorded per file; one receipt goes into the DAY directory. Refuses when the cycle holds
# a critic dispatch (then the old readiness was USED and is evidence). Re-runnable. Starts, stops and
# dispatches nothing; never reads the SSM credential parameter.
#
# $Day, $RunRoot and $ToolsRoot arrive from ssm_run_ps1.py --set; no path literal here.
$ErrorActionPreference = 'Stop'
foreach ($required in 'Day', 'RunRoot', 'ToolsRoot') {
    $value = Get-Variable -Name $required -ValueOnly -ErrorAction SilentlyContinue
    if (-not $value -or $value -like 'HOST_*') { throw "$required was not supplied by ssm_run_ps1.py --set (value: '$value')" }
}
if (-not (Get-Variable CycleIndex -ErrorAction SilentlyContinue)) { $CycleIndex = '00' }
if ($CycleIndex -notmatch '^\d{2}$') { throw "CycleIndex must be two digits (value: '$CycleIndex')" }
$dayDirectory = Join-Path $RunRoot $Day
$cfgPath = Join-Path $dayDirectory 'actual-host-configuration.json'
if (-not (Test-Path $cfgPath)) { throw "no run configuration for $Day at $cfgPath" }
$cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
$runDirectory = $cfg.run_directory
if (-not $runDirectory -or -not (Test-Path $runDirectory)) { throw "run_directory absent: $runDirectory" }
$git = (Get-Command git -ErrorAction Stop).Source
$head = (& $git -C $ToolsRoot rev-parse HEAD).Trim()
if ($head -ne $cfg.host_runtime.boss_commit) { throw ("refusing: tools HEAD " + $head + " is not the configuration's boss_commit " + $cfg.host_runtime.boss_commit) }
$requestId = $cfg.run_id + '-cycle-' + $CycleIndex
$triggerRoot = $cfg.host_runtime.pod_credential_ssm.trigger_directory
if (-not $triggerRoot) { throw 'host configuration declares no trigger_directory' }
$cycle = Join-Path $runDirectory ('execution\cycle-' + $CycleIndex)
if (-not (Test-Path $cycle)) { throw ("cycle directory absent: " + $cycle) }
$spool = Join-Path $cycle 'critic-spool'
if ((Test-Path $spool) -and @(Get-ChildItem $spool -Recurse -Filter 'dispatch.json' -ErrorAction SilentlyContinue).Count -gt 0) {
    throw ("refusing: cycle " + $CycleIndex + " holds a critic dispatch; its readiness was used and is evidence")
}
$triggerDir = Join-Path $triggerRoot $requestId
$readinessDir = $null
$triggerFile = Join-Path $triggerDir 'FRANKIE_ACTUAL_EXECUTE_V1.json'
if (Test-Path $triggerFile) {
    $trigger = Get-Content $triggerFile -Raw | ConvertFrom-Json
    $readinessDir = $trigger.readiness_directory
    Write-Output ("trigger names readiness_directory = " + $readinessDir)
} else { Write-Output ("no trigger at " + $triggerFile) }
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$target = Join-Path (Join-Path (Split-Path $RunRoot -Parent) 'superseded') ('readiness-' + $stamp + '-' + $requestId)
$sha = [System.Security.Cryptography.SHA256]::Create()
$moved = @()
function Move-Recorded([string]$source, [string]$label) {
    if (-not (Test-Path $source)) { Write-Output ("  absent, skipped: " + $label); return }
    $item = Get-Item $source
    $files = if ($item.PSIsContainer) { @(Get-ChildItem $source -Recurse -File) } else { @($item) }
    $entries = @()
    foreach ($file in $files) {
        if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw ("refusing: reparse point under " + $label) }
        $digest = ([BitConverter]::ToString($script:sha.ComputeHash([IO.File]::ReadAllBytes($file.FullName)))).Replace('-', '').ToLower()
        $entries += [ordered]@{ path = $file.FullName; sha256 = $digest; bytes = [int64]$file.Length; mtime_utc = $file.LastWriteTimeUtc.ToString('s') + 'Z' }
    }
    $destination = Join-Path $script:target $label
    New-Item -ItemType Directory -Force -Path (Split-Path $destination -Parent) | Out-Null
    Move-Item -LiteralPath $source -Destination $destination
    if (Test-Path $source) { throw ("move left the source in place: " + $label) }
    if (-not (Test-Path $destination)) { throw ("move lost the item: " + $label) }
    $script:moved += [ordered]@{ label = $label; source = $source; destination = $destination; files = $entries }
    Write-Output ("  moved: " + $label + "  (" + $entries.Count + " file(s))")
}
Move-Recorded $triggerDir ('triggers/' + $requestId)
if ($readinessDir) { Move-Recorded $readinessDir ('readiness/' + $requestId) }
Move-Recorded (Join-Path $cycle 'host-service.c15.json') ('execution/cycle-' + $CycleIndex + '/host-service.c15.json')
$receipt = [ordered]@{
    schema          = 'FRANKIE_READINESS_SUPERSEDED_V1'
    day             = $Day
    run_id          = $cfg.run_id
    request_id      = $requestId
    boss_commit     = $head
    reason          = 'delivered readiness pins the CRLF-era request 6cd46f98...; the normalized host prepares a7b72cf9... (run 35517953486 line 833); a re-pinned readiness must be delivered and the trigger is immutable'
    superseded_root = $(if ($moved.Count -gt 0) { $target } else { $null })
    kept            = @('host-preparation.c15.json', 'host-ready-*.c15.json', 'actual-critic-request.json', 'host-context-cache.c15.json')
    moved           = $moved
    at              = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
}
$receiptPath = Join-Path $dayDirectory ('superseded-readiness-' + $stamp + '.json')
Set-Content -Path $receiptPath -Value ($receipt | ConvertTo-Json -Depth 8) -NoNewline -Encoding UTF8
Write-Output ("receipt: " + $receiptPath)
Write-Output ('RECEIPT ' + ($receipt | ConvertTo-Json -Depth 8 -Compress))
