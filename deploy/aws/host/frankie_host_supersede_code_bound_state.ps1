# Supersede the code-bound retained state of a run directory so the runner can re-enter it at the
# advanced host commit. Greg's call, 2026-09-20: get the 20211003 two-cycle run running; the
# identity guard is secondary unless it changes the cycle calculations, and it does not.
#
# Why these files (probe runs 35510320789 / 35510506738 / 35510597019, pipeline 35511984264, code read):
#   run_actual_sunday.py __init__ saves host-identity.c15.json (configuration + every code hash);
#   _training saves initialization.c15.json (identities incl. code_hash) and creates training.sqlite
#   whose checkpoint DIGEST encodes those identities (boss_training_checkpoint.py 158/210), witnessed
#   by training-witnesses/state-*.c15.json; that digest is pinned by cycle-NN/host-preparation.c15.json
#   (initial_checkpoint_hash), host-ready-<instance>.c15.json (checkpoint_hash),
#   host-context-cache.c15.json (prepared_context_cache.py 142) and request-plan.c15.json
#   (sunday_execution.py 268); actual-critic-request.json must be byte-identical to the re-prepared
#   body or the runner refuses. sunday_execution.SundayExecution.__init__ saves
#   execution/execution-identity.c15.json with boss_commit (line 213): that one refused pipeline run
#   35511984264 after the first eight were moved. sunday_execution._save refuses any of these on
#   differing bytes ('retained Sunday execution evidence changed').
#   Beyond the enumerated set, every *.c15.json under the run directory is scanned for the OLD
#   boss_commit literal and any hit is moved too, so an unenumerated boss_commit binding cannot refuse
#   the next dispatch. Everything else is data-derived and stays: host-instance.c15.json (the
#   instance id the delivered readiness is bound to; line 837), native-host-runtime.json (the
#   --ec2-resume marker, already accepted at the advanced commit), verified-*, host-prefix,
#   the classroom package, cycles.sqlite / lessons.sqlite.
#
# NOTHING IS DELETED. Each item is MOVED, relative path preserved, into a sibling folder
# <run_directory parent>/superseded/<run dir name>-<stamp>-code-<old boss_commit>/ so no stray
# name remains inside the run directory for any glob to pick up. A receipt with every moved path
# and its sha256 is written into the DAY directory (as the advance script keeps its backup there).
# Refuses unless the tools checkout HEAD equals the configuration's boss_commit (we only supersede
# to run at the commit the configuration names). The old commit is read from host-identity.c15.json
# or, once that is gone, from execution/execution-identity.c15.json; when neither is present and
# nothing is stale, the receipt says so and nothing moves. Re-runnable. Starts, stops and
# dispatches nothing.
#
# $Day, $RunRoot, $ToolsRoot and $Python arrive from ssm_run_ps1.py --set; no path literal here.
$ErrorActionPreference = 'Stop'
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
$runDirectory = $cfg.run_directory
if (-not $runDirectory -or -not (Test-Path $runDirectory)) { throw "run_directory absent: $runDirectory" }
# run_directory is interpolated into a raw Python literal below; a quote or newline would end it.
if ($runDirectory -match "[\x27\x22\r\n]") { throw 'refusing: run_directory carries a quote or newline' }
$git = (Get-Command git -ErrorAction Stop).Source
$head = (& $git -C $ToolsRoot rev-parse HEAD).Trim()
if ($head -ne $cfg.host_runtime.boss_commit) { throw ("refusing: tools HEAD " + $head + " is not the configuration's boss_commit " + $cfg.host_runtime.boss_commit) }
if (-not (Test-Path (Join-Path $runDirectory 'host-instance.c15.json'))) { throw 'refusing: host-instance.c15.json absent; the delivered readiness is bound to it' }

# The stored (old) boss_commit, read through the host's own unpack so the c15 shape is honoured.
$env:PYTHONDONTWRITEBYTECODE = '1'; $env:PYTHONPATH = $ToolsRoot
$code = @"
import json, sys
from pathlib import Path
sys.path.insert(0, r'$ToolsRoot')
from research.kalshi.frankie_boss.c15_journal import unpack
run = Path(r'$runDirectory')
# Both identity records, each on its own line: a fresh host-identity written by a refused run
# must not mask a stale execution-identity (pipeline 35511984264 did exactly that).
for path, pick in ((run / 'host-identity.c15.json', lambda v: v['configuration']['host_runtime']['boss_commit']),
                   (run / 'execution' / 'execution-identity.c15.json', lambda v: v['boss_commit'])):
    print(pick(unpack(json.loads(path.read_bytes()))) if path.exists() else 'absent')
"@
$identities = @(& $Python -c $code 2>&1 | Select-Object -Last 2 | ForEach-Object { $_.ToString().Trim() })
if ($identities.Count -ne 2) { throw ("could not read the identity records: " + ($identities -join ' | ')) }
$hostIdentity = $identities[0]; $executionIdentity = $identities[1]
foreach ($value in $identities) { if ($value -ne 'absent' -and $value -notmatch '^[0-9a-f]{40}$') { throw ("could not read a stored boss_commit: " + $value) } }
Write-Output ("host-identity boss_commit:      " + $hostIdentity)
Write-Output ("execution-identity boss_commit: " + $executionIdentity)
Write-Output ("current (tools HEAD):           " + $head)
# The OLD commit is whichever stored identity differs from the current one.
$stored = 'absent'
foreach ($value in $identities) { if ($value -ne 'absent' -and $value -ne $head) { $stored = $value; break } }
if ($stored -eq 'absent' -and ($hostIdentity -eq $head -or $executionIdentity -eq $head)) { $stored = $head }
# Once both identity records are gone (a prior dispatch moved them and then threw on a later item),
# nothing on disk names the old commit; the operator supplies it, and the leftover check below refuses
# to report success while checkpoint-bound records remain unjudged.
if ((Get-Variable OldCommit -ErrorAction SilentlyContinue) -and $OldCommit) {
    if ($OldCommit -notmatch '^[0-9a-f]{40}$') { throw 'OldCommit must be a full 40-hex commit' }
    if ($OldCommit -eq $head) { throw 'OldCommit equals the current commit; nothing to supersede' }
    if ($stored -ne 'absent' -and $stored -ne $OldCommit) { throw ("OldCommit " + $OldCommit + " contradicts the stored identity " + $stored) }
    $stored = $OldCommit
    Write-Output ("old commit supplied by the operator: " + $OldCommit)
}

$moved = @()
$candidates = @()
if ($stored -ne 'absent' -and $stored -ne $head) {
    $cycleRelative = 'execution/cycle-' + $CycleIndex
    $cycle = Join-Path $runDirectory $cycleRelative
    # An identity record is moved only when it is the stale one; a fresh record written by a
    # refused run at the current commit is exactly what the next run re-saves byte for byte.
    $candidates = @('initialization.c15.json', 'training.sqlite', 'training-witnesses')
    if ($hostIdentity -ne 'absent' -and $hostIdentity -ne $head) { $candidates += 'host-identity.c15.json' }
    if ($executionIdentity -ne 'absent' -and $executionIdentity -ne $head) { $candidates += 'execution/execution-identity.c15.json' }
    $candidates += @(
        ($cycleRelative + '/host-preparation.c15.json'),
        ($cycleRelative + '/host-service.c15.json'),
        ($cycleRelative + '/host-context-cache.c15.json'),
        ($cycleRelative + '/request-plan.c15.json'),
        ($cycleRelative + '/actual-critic-request.json'))
    if (Test-Path $cycle) {
        Get-ChildItem $cycle -Filter 'host-ready-*.c15.json' | ForEach-Object { $candidates += ($cycleRelative + '/' + $_.Name) }
    }
    # Catch-all for an unenumerated record carrying the OLD commit literal, scoped to this run's root,
    # the execution root and THIS cycle only: another cycle's completion.c15.json carries boss_commit
    # lawfully and must stay. Kept records and chained journals (genesis/append-*) are never moved;
    # reparse points are never followed; nothing outside the resolved run root is touched.
    $root = (Resolve-Path $runDirectory).Path
    $reparse = [IO.FileAttributes]::ReparsePoint
    foreach ($scanRoot in @($runDirectory, (Join-Path $runDirectory 'execution'), $cycle)) {
        if (-not (Test-Path $scanRoot)) { continue }
        Get-ChildItem $scanRoot -File -Filter '*.c15.json' | Where-Object { -not ($_.Attributes -band $reparse) } | ForEach-Object {
            if (-not $_.FullName.StartsWith($root)) { return }
            $name = $_.Name
            if ($name -eq 'host-instance.c15.json' -or $name -like 'verified-*' -or $name -eq 'genesis.c15.json' -or $name -like 'append-*') { return }
            $relative = $_.FullName.Substring($root.Length).TrimStart('\', '/').Replace('\', '/')
            if ($candidates -notcontains $relative) {
                if (Select-String -Path $_.FullName -SimpleMatch $stored -Quiet) {
                    Write-Output ("  scan hit (old commit literal): " + $relative)
                    $candidates += $relative
                }
            }
        }
    }
} elseif ($stored -eq $head) {
    Write-Output 'stored identity already matches the current commit; nothing is stale'
} else {
    Write-Output 'no stored identity found'
    # With no identity to judge by, a leftover checkpoint-bound record cannot be called fresh.
    $cycleRelative = 'execution/cycle-' + $CycleIndex
    $leftovers = @('initialization.c15.json', 'training.sqlite', 'training-witnesses',
        ($cycleRelative + '/host-preparation.c15.json'), ($cycleRelative + '/host-context-cache.c15.json'),
        ($cycleRelative + '/request-plan.c15.json'), ($cycleRelative + '/actual-critic-request.json')) |
        Where-Object { Test-Path (Join-Path $runDirectory $_) }
    if ($leftovers) { throw ("refusing: no identity record to judge by, but checkpoint-bound records are present: " + ($leftovers -join ', ') + ". Supply OldCommit if they are stale.") }
    Write-Output 'nothing is stale'
}

$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$runName = Split-Path $runDirectory -Leaf
$target = Join-Path (Join-Path (Split-Path $runDirectory -Parent) 'superseded') ($runName + '-' + $stamp + '-code-' + $stored)
$sha = [System.Security.Cryptography.SHA256]::Create()
foreach ($relative in $candidates) {
    $source = Join-Path $runDirectory $relative
    if (-not (Test-Path $source)) { Write-Output ("  absent, skipped: " + $relative); continue }
    $destination = Join-Path $target $relative
    New-Item -ItemType Directory -Force -Path (Split-Path $destination -Parent) | Out-Null
    $item = Get-Item $source
    $digest = $null; $bytes = $null
    if (-not $item.PSIsContainer) {
        $digest = ([BitConverter]::ToString($sha.ComputeHash([IO.File]::ReadAllBytes($source)))).Replace('-', '').ToLower()
        $bytes = $item.Length
    }
    Move-Item -LiteralPath $source -Destination $destination
    if (Test-Path $source) { throw ("move left the source in place: " + $relative) }
    if (-not (Test-Path $destination)) { throw ("move lost the item: " + $relative) }
    $moved += [ordered]@{ relative = $relative; destination = $destination; sha256 = $digest; bytes = $bytes; mtime_utc = $item.LastWriteTimeUtc.ToString('s') + 'Z' }
    Write-Output ("  moved: " + $relative + "  sha256=" + $digest)
}
$receipt = [ordered]@{
    schema              = 'FRANKIE_CODE_BOUND_STATE_SUPERSEDED_V1'
    day                 = $Day
    run_id              = $cfg.run_id
    run_directory       = $runDirectory
    stored_boss_commit  = $stored
    current_boss_commit = $head
    stale               = ($stored -ne 'absent' -and $stored -ne $head)
    superseded_root     = $(if ($moved.Count -gt 0) { $target } else { $null })
    kept                = @('host-instance.c15.json', 'native-host-runtime.json')
    moved               = $moved
    at                  = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
}
$receiptPath = Join-Path $dayDirectory ('superseded-code-bound-state-' + $stamp + '.json')
Set-Content -Path $receiptPath -Value ($receipt | ConvertTo-Json -Depth 6) -NoNewline -Encoding UTF8
Write-Output ("receipt: " + $receiptPath)
Write-Output ('RECEIPT ' + ($receipt | ConvertTo-Json -Depth 6 -Compress))
