# Declare, for one cycle, that its saved binding may be superseded by the current code identity
# (2026-09-20). Read CLAUDE_HANDOFF_20260920.md ("cycle request identity changed").
#
# Why: pipeline run 35525830210 resumed cycle 0 on the advanced checkout, re-prepared it and passed
# the readiness pins, then feedback_cycle.run refused 'cycle request identity changed': the saved
# binding pins training_identities.code_hash (every source file's hash), which the advance changed.
# The coordinator accepts that ONE difference only against an explicit declaration next to the
# cycle store; this script makes it through the checked-in helper
# research/kalshi/frankie_boss/operations/declare_identity_supersede.py (reads the OLD hash from the
# saved binding, computes the CURRENT identity from the tools checkout, appends the declaration,
# writes a receipt into the day directory). Refuses while a runner process is alive. Writes only
# the declaration and the receipt; never touches the cycle store or the credential.
#
# $Day, $RunRoot, $ToolsRoot, $Python, $CycleIndex, $Reason, $SupersedePrincipal, $SupersedeCycle arrive from ssm_run_ps1.py --set; no path literal here.
$ErrorActionPreference = 'Stop'
foreach ($required in 'Day', 'RunRoot', 'ToolsRoot', 'Python', 'Reason') {
    $value = Get-Variable -Name $required -ValueOnly -ErrorAction SilentlyContinue
    if (-not $value -or $value -like 'HOST_*') { throw "$required was not supplied by ssm_run_ps1.py --set (value: '$value')" }
}
if (-not (Get-Variable CycleIndex -ErrorAction SilentlyContinue)) { $CycleIndex = '00' }
if ($CycleIndex -notmatch '^\d{2}$') { throw "CycleIndex must be two digits (value: '$CycleIndex')" }
# Greg, 2026-09-20: 'true' also declares that the cycle's saved principal attachment and intent may be
# superseded so the principal request is rendered again (the run-findings ledger enters the prompt).
if (-not (Get-Variable SupersedePrincipal -ErrorAction SilentlyContinue)) { $SupersedePrincipal = 'false' }
if ($SupersedePrincipal -notin @('true', 'false')) { throw "SupersedePrincipal must be true or false (value: '$SupersedePrincipal')" }
$principalArgs = @(); if ($SupersedePrincipal -eq 'true') { $principalArgs = @('--supersede-principal') }
# Greg, 2026-09-20 ("a full rerun from the beginning and not steps"): 'true' also declares that EVERY live
# stage of the open cycle may be superseded so it runs again from the beginning under the current code.
if (-not (Get-Variable SupersedeCycle -ErrorAction SilentlyContinue)) { $SupersedeCycle = 'false' }
if ($SupersedeCycle -notin @('true', 'false')) { throw "SupersedeCycle must be true or false (value: '$SupersedeCycle')" }
if ($SupersedeCycle -eq 'true') { $principalArgs += @('--supersede-cycle') }
$dayDirectory = Join-Path $RunRoot $Day
$cfgPath = Join-Path $dayDirectory 'actual-host-configuration.json'
if (-not (Test-Path $cfgPath)) { throw "no run configuration for $Day at $cfgPath" }
$cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
$runDirectory = $cfg.run_directory
if (-not $runDirectory -or -not (Test-Path $runDirectory)) { throw "run_directory absent: $runDirectory" }
if (-not (Test-Path $Python)) { throw "host python missing: $Python" }
$git = (Get-Command git -ErrorAction Stop).Source
$head = (& $git -C $ToolsRoot rev-parse HEAD).Trim()
if ($head -ne $cfg.host_runtime.boss_commit) { throw ("refusing: tools HEAD " + $head + " is not the configuration's boss_commit " + $cfg.host_runtime.boss_commit) }
$alive = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*run_actual_sunday*' })
if ($alive.Count -gt 0) { throw ("refusing: a runner process is alive (pid " + ($alive | ForEach-Object { $_.ProcessId }) + ")") }
$requestId = $cfg.run_id + '-cycle-' + $CycleIndex
$helper = Join-Path $ToolsRoot 'research/kalshi/frankie_boss/operations/declare_identity_supersede.py'
if (-not (Test-Path $helper)) { throw "helper missing on this checkout: $helper" }
$env:PYTHONPATH = $ToolsRoot
Write-Output ("declaring for " + $requestId + " at tools HEAD " + $head)
& $Python $helper --run-directory $runDirectory --tools-root $ToolsRoot --request-id $requestId --reason $Reason --receipt-directory $dayDirectory @principalArgs
if ($LASTEXITCODE -ne 0) { throw ("declaration helper exited " + $LASTEXITCODE) }
