# Supersede the retained Dipole classroom package of one cycle so the runner rebuilds it (2026-09-20).
#
# Why: pipeline run 35517121900's stop record (frames, 34a4feac) ends at
# run_actual_sunday_classroom.py:191 prime_cache -> sunday_execution.py:48 _save: the runner rebuilds
# the classroom package for the cycle (source, teacher-key, pre-message, binding) from the CURRENT
# code and the prepared context and saves it into the cycle directory, where the package written on
# 2026-09-17 05:25Z by the prepare-only run (older code, the initial training identity since
# re-minted) still sits; _save refuses on differing bytes ('retained Sunday execution evidence
# changed'). The supersede of code-bound state deliberately kept that package as data-derived; the
# frames show it is not. Cycle 0 never ran inference on it, so nothing learned is lost.
#
# NOTHING IS DELETED: the four files are MOVED, relative path preserved, into
# <run_directory parent>/superseded/<run dir name>-<stamp>-classroom-cycle-<NN>/ with sha256, bytes
# and mtime recorded, and one receipt is written into the DAY directory. The adapter identity record
# (host-dipole-classroom-adapter.c15.json) is re-saved byte for byte by the runner and stays. Refuses
# unless the tools checkout HEAD equals the configuration's boss_commit and refuses while a
# principal completion for the cycle exists (then the package was USED and is evidence). Re-runnable.
# Starts, stops and dispatches nothing.
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
$cycleRelative = 'execution/cycle-' + $CycleIndex
$cycle = Join-Path $runDirectory $cycleRelative
if (-not (Test-Path $cycle)) { throw ("cycle directory absent: " + $cycle) }
$completion = Join-Path $cycle 'principal\dipole-classroom-completion.json'
if (Test-Path $completion) { throw ("refusing: cycle " + $CycleIndex + " holds a Dipole classroom completion; its package is evidence, not retained preparation") }
$names = @('source', 'teacher-key', 'pre-message', 'binding') | ForEach-Object { 'host-dipole-classroom-' + $_ + '.c15.json' }
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$runName = Split-Path $runDirectory -Leaf
$target = Join-Path (Join-Path (Split-Path $runDirectory -Parent) 'superseded') ($runName + '-' + $stamp + '-classroom-cycle-' + $CycleIndex)
$sha = [System.Security.Cryptography.SHA256]::Create()
$moved = @()
foreach ($name in $names) {
    $relative = $cycleRelative + '/' + $name
    $source = Join-Path $cycle $name
    if (-not (Test-Path $source)) { Write-Output ("  absent, skipped: " + $relative); continue }
    $item = Get-Item $source
    if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw ("refusing: not a plain file: " + $relative) }
    $destination = Join-Path $target $relative
    New-Item -ItemType Directory -Force -Path (Split-Path $destination -Parent) | Out-Null
    $bytes = [int64]$item.Length; $mtime = $item.LastWriteTimeUtc.ToString('s') + 'Z'   # read BEFORE the move
    $digest = ([BitConverter]::ToString($sha.ComputeHash([IO.File]::ReadAllBytes($source)))).Replace('-', '').ToLower()
    Move-Item -LiteralPath $source -Destination $destination
    if (Test-Path $source) { throw ("move left the source in place: " + $relative) }
    if (-not (Test-Path $destination)) { throw ("move lost the item: " + $relative) }
    $moved += [ordered]@{ relative = $relative; destination = $destination; sha256 = $digest; bytes = $bytes; mtime_utc = $mtime }
    Write-Output ("  moved: " + $relative + "  sha256=" + $digest + "  bytes=" + $bytes)
}
$receipt = [ordered]@{
    schema          = 'FRANKIE_CLASSROOM_PACKAGE_SUPERSEDED_V1'
    day             = $Day
    run_id          = $cfg.run_id
    run_directory   = $runDirectory
    cycle_index     = $CycleIndex
    boss_commit     = $head
    reason          = 'run_actual_sunday_classroom.prime_cache rebuilds the package and _save refused the retained 2026-09-17 bytes (pipeline run 35517121900 frames)'
    superseded_root = $(if ($moved.Count -gt 0) { $target } else { $null })
    kept            = @('host-dipole-classroom-adapter.c15.json')
    moved           = $moved
    at              = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
}
$receiptPath = Join-Path $dayDirectory ('superseded-classroom-package-' + $stamp + '.json')
Set-Content -Path $receiptPath -Value ($receipt | ConvertTo-Json -Depth 6) -NoNewline -Encoding UTF8
Write-Output ("receipt: " + $receiptPath)
Write-Output ('RECEIPT ' + ($receipt | ConvertTo-Json -Depth 6 -Compress))
