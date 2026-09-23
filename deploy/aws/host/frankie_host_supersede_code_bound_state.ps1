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
# and its sha256 is written into the DAY directory. A flushed intent lists all selected bytes
# before any move; retries reconcile unfinished intents before reading potentially moved identities.
# Per-move receipts and completion retain the same intent hash. Existing evidence is never overwritten.
# Refuses unless the tools checkout HEAD equals the configuration's boss_commit (we only supersede
# to run at the commit the configuration names). The old commit is read from host-identity.c15.json
# or, once that is gone, from execution/execution-identity.c15.json; when neither is present and
# nothing is stale, the receipt says so and nothing moves. Re-runnable. Starts, stops and
# dispatches nothing.
#
# $Day, $RunRoot, $ToolsRoot and $Python arrive from ssm_run_ps1.py --set; no path literal here.
$ErrorActionPreference = 'Stop'

# These functions operate only on operator-selected run evidence. A link in any
# existing ancestor is refused before inspection, hashing, directory creation or move.
function Test-StateWithin([string]$Path, [string]$Root) {
    $comparison = [StringComparison]::Ordinal
    if ([IO.Path]::DirectorySeparatorChar -eq '\') { $comparison = [StringComparison]::OrdinalIgnoreCase }
    $base = [IO.Path]::GetFullPath($Root).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    $full = [IO.Path]::GetFullPath($Path)
    return $full.StartsWith($base + [IO.Path]::DirectorySeparatorChar, $comparison)
}

function Test-StateSame([string]$Left, [string]$Right) {
    $comparison = [StringComparison]::Ordinal
    if ([IO.Path]::DirectorySeparatorChar -eq '\') { $comparison = [StringComparison]::OrdinalIgnoreCase }
    $a = [IO.Path]::GetFullPath($Left).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    $b = [IO.Path]::GetFullPath($Right).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    return [string]::Equals($a, $b, $comparison)
}

function Assert-StatePath([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    if ($full.Length -gt [IO.Path]::GetPathRoot($full).Length) {
        $full = $full.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    }
    $cursor = $full
    while ($cursor) {
        $item = Get-Item -LiteralPath $cursor -Force -ErrorAction SilentlyContinue
        if ($item -and ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw ("refusing reparse point: " + $cursor)
        }
        $parent = [IO.Path]::GetDirectoryName($cursor)
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
    return $full
}

function Get-StateHash([string]$Path) {
    $stream = [IO.File]::OpenRead((Assert-StatePath $Path))
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($hasher.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $hasher.Dispose() }
}

function Get-StateManifest([string]$Path) {
    $base = Assert-StatePath $Path
    $pending = [Collections.Generic.Stack[string]]::new()
    $pending.Push($base)
    $entries = @()
    while ($pending.Count -gt 0) {
        $current = Assert-StatePath ($pending.Pop())
        $item = Get-Item -LiteralPath $current -Force -ErrorAction Stop
        $relative = '.'
        if ($current -ne $base) {
            if (-not (Test-StateWithin $current $base)) { throw 'manifest escaped selected item' }
            $relative = $current.Substring($base.Length).TrimStart('\', '/').Replace('\', '/')
        }
        if ($item.PSIsContainer) {
            $entries += [ordered]@{ relative = $relative; kind = 'directory'; sha256 = $null; bytes = $null }
            foreach ($child in @(Get-ChildItem -LiteralPath $current -Force)) { $pending.Push($child.FullName) }
        } else {
            $entries += [ordered]@{ relative = $relative; kind = 'file'; sha256 = (Get-StateHash $current); bytes = $item.Length }
        }
    }
    return @($entries | Sort-Object { $_.relative })
}

function Write-StateJson([string]$Path, $Value) {
    $full = Assert-StatePath $Path
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($Value | ConvertTo-Json -Depth 20 -Compress))
    # A crash while writing leaves only a pending sibling. Discovery considers
    # published JSON names, so retained partial bytes cannot masquerade as a receipt.
    $pending = Assert-StatePath ($full + '.pending-' + [Guid]::NewGuid().ToString('N'))
    $stream = [IO.File]::Open($pending, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
    $null = Assert-StatePath $full
    $null = Assert-StatePath $pending
    # Same-directory publish is atomic; the two-argument API refuses any existing final name.
    # Orphan pending files remain intact for inspection after a refused publish.
    [IO.File]::Move($pending, $full)
}

function Assert-StateManifest([string]$Path, $Expected) {
    $actual = @(Get-StateManifest $Path) | ConvertTo-Json -Depth 20 -Compress
    $expectedJson = @($Expected) | ConvertTo-Json -Depth 20 -Compress
    if ($actual -cne $expectedJson) { throw ("preserved bytes differ from intent: " + $Path) }
}

function Assert-ForeignStateIntents([string]$OwnSchema) {
    $families = @(
        @{ prefix = 'superseded-code-bound-state-'; intent = 'FRANKIE_CODE_BOUND_STATE_INTENT_V1'; completion = 'FRANKIE_CODE_BOUND_STATE_SUPERSEDED_V1' },
        @{ prefix = 'principal-response-superseded-'; intent = 'FRANKIE_PRINCIPAL_RESPONSE_INTENT_V1'; completion = 'FRANKIE_PRINCIPAL_RESPONSE_SUPERSEDED_V1' },
        @{ prefix = 'cycle-state-superseded-'; intent = 'FRANKIE_CYCLE_STATE_INTENT_V1'; completion = 'FRANKIE_CYCLE_STATE_SUPERSEDED_V1' }
    )
    foreach ($family in $families) {
        if ($family.intent -eq $OwnSchema) { continue }
        foreach ($file in @(Get-ChildItem -LiteralPath $dayDirectory -Filter ($family.prefix + '*.intent.json') -Force)) {
            $path = Assert-StatePath $file.FullName
            if ($file.PSIsContainer) { throw 'foreign intent is not a file' }
            $prior = Get-Content -LiteralPath $path -Encoding UTF8 -Raw | ConvertFrom-Json
            if ($prior.schema -cne $family.intent -or -not $prior.run_directory) { throw 'malformed foreign preservation intent' }
            $completion = Assert-StatePath ($path.Substring(0, $path.Length - '.intent.json'.Length) + '.json')
            if (-not (Test-Path -LiteralPath $completion)) { throw 'unfinished foreign preservation intent requires its own helper' }
            $done = Get-Content -LiteralPath $completion -Encoding UTF8 -Raw | ConvertFrom-Json
            if ($done.schema -cne $family.completion -or -not $done.intent_path -or
                -not (Test-StateSame $done.intent_path $path) -or $done.intent_sha256 -cne (Get-StateHash $path)) {
                throw 'foreign completion does not bind its retained intent'
            }
        }
    }
}

function Assert-RunnerIdle {
    # The helper lock serializes helpers, not runtime creation. Refuse any
    # inventory that cannot establish an idle runner; never stop a process.
    $inventory = @(Get-CimInstance Win32_Process -ErrorAction Stop)
    if ($inventory.Count -eq 0) { throw 'refusing: process inventory is empty' }
    foreach ($process in $inventory) {
        if ($process.Name -isnot [string] -or [string]::IsNullOrWhiteSpace($process.Name)) {
            throw 'refusing: process inventory has no evaluable process name'
        }
        if ($process.Name -match '^(?:python[^/\\]*|pyw?)(?:\.exe)?$' -and
            ($process.CommandLine -isnot [string] -or [string]::IsNullOrWhiteSpace($process.CommandLine))) {
            throw 'refusing: Python process command line is unavailable'
        }
        if ($process.CommandLine -like '*run_actual_sunday*') {
            throw ('refusing: a runner process is alive (pid ' + $process.ProcessId + ')')
        }
    }
}

function Complete-StateIntent([string]$IntentPath) {
    $null = Assert-StatePath $IntentPath
    $intent = Get-Content -LiteralPath $IntentPath -Encoding UTF8 -Raw | ConvertFrom-Json
    if ($intent.schema -ne 'FRANKIE_CODE_BOUND_STATE_INTENT_V1' -or
        -not (Test-StateSame $intent.run_directory $runDirectory) -or $intent.run_id -cne $cfg.run_id -or
        $intent.day -cne $Day -or $intent.cycle_index -cne $CycleIndex -or
        $intent.current_boss_commit -cne $head -or
        $intent.stored_boss_commit -notmatch '^(absent|[0-9a-f]{40})$') {
        throw ("unfinished intent does not match this run/cycle/commit: " + $IntentPath)
    }
    $stem = $IntentPath.Substring(0, $IntentPath.Length - '.intent.json'.Length)
    $receiptPath = $stem + '.json'
    $target = Assert-StatePath $intent.superseded_root
    $archiveRoot = Assert-StatePath (Join-Path (Split-Path $runDirectory -Parent) 'superseded')
    if (-not (Test-StateWithin $target $archiveRoot) -or
        (Test-StateWithin $target $runDirectory) -or (Test-StateSame $target $runDirectory)) {
        throw 'intent destination escaped the sibling archive'
    }
    if ($null -eq $intent.items -or $intent.items -isnot [Array]) { throw 'intent items must be an array' }
    $intentHash = Get-StateHash $IntentPath
    $seen = @{}
    $expectedMoveReceiptPaths = @{}
    $preflightIndex = 0
    # Validate EVERY path, manifest and retained receipt before the first reconciliation move.
    foreach ($entry in $intent.items) {
        $relative = [string]$entry.relative
        if (-not $relative -or [IO.Path]::IsPathRooted($relative) -or
            @($relative.Replace('\', '/').Split('/') | Where-Object { $_ -in @('', '.', '..') }).Count -gt 0 -or
            $seen.ContainsKey($relative)) { throw 'invalid or duplicate intent relative path' }
        $seen[$relative] = $true
        $source = Assert-StatePath (Join-Path $runDirectory $relative)
        $destination = Assert-StatePath (Join-Path $target $relative)
        if (-not (Test-StateWithin $source $runDirectory) -or
            -not (Test-StateWithin $destination $target) -or
            -not (Test-StateSame $entry.destination $destination)) { throw 'intent path escaped its root' }
        $parts = $relative.Replace('\', '/').Split('/')
        $name = $parts[-1]
        $scopeAllowed = ($parts.Count -eq 1) -or
            ($parts.Count -eq 2 -and $parts[0] -eq 'execution') -or
            ($parts.Count -eq 3 -and $parts[0] -eq 'execution' -and $parts[1] -eq ('cycle-' + $CycleIndex))
        $nameAllowed = $name.EndsWith('.c15.json') -or
            ($parts.Count -eq 1 -and $name -in @('training.sqlite', 'training-witnesses')) -or
            ($parts.Count -eq 3 -and $name -eq 'actual-critic-request.json')
        if (-not $scopeAllowed -or -not $nameAllowed -or $name -like 'verified-*' -or
            $name -eq 'genesis.c15.json' -or $name -like 'append-*') { throw 'intent selects unapproved evidence' }
        if ($relative -in @('host-instance.c15.json', 'native-host-runtime.json') -or
            ($relative -like 'execution/cycle-*/*' -and -not $relative.StartsWith('execution/cycle-' + $CycleIndex + '/'))) {
            throw 'intent selects kept or other-cycle evidence'
        }
        if ($null -eq $entry.manifest -or $entry.manifest -isnot [Array] -or $entry.manifest.Count -eq 0) {
            throw 'intent lacks a complete manifest'
        }
        $atSource = Test-Path -LiteralPath $source
        $atDestination = Test-Path -LiteralPath $destination
        if ($atSource -eq $atDestination) { throw ("ambiguous or missing preserved item: " + $relative) }
        if ($atSource) { Assert-StateManifest $source $entry.manifest }
        else { Assert-StateManifest $destination $entry.manifest }
        $preflightReceiptPath = Assert-StatePath ($stem + '.move-' + $preflightIndex + '.json')
        $expectedMoveReceiptPaths[$preflightReceiptPath] = $true
        if (Test-Path -LiteralPath $preflightReceiptPath) {
            if ($atSource) { throw 'move receipt exists but source is present' }
            $retainedReceipt = Get-Content -LiteralPath $preflightReceiptPath -Encoding UTF8 -Raw | ConvertFrom-Json
            $expectedReceipt = [ordered]@{ schema = 'FRANKIE_CODE_BOUND_STATE_MOVE_V1'; intent_sha256 = $intentHash; item = $entry }
            if (($retainedReceipt | ConvertTo-Json -Depth 20 -Compress) -cne ($expectedReceipt | ConvertTo-Json -Depth 20 -Compress)) {
                throw 'move receipt differs from intent'
            }
        }
        $preflightIndex += 1
    }
    $receiptFilter = (Split-Path $stem -Leaf) + '.move-*.json'
    foreach ($retainedFile in @(Get-ChildItem -LiteralPath (Split-Path $stem -Parent) -Filter $receiptFilter -Force)) {
        $retainedPath = Assert-StatePath $retainedFile.FullName
        if (-not $expectedMoveReceiptPaths.ContainsKey($retainedPath)) { throw 'unexpected move receipt outside intent' }
    }
    Assert-RunnerIdle
    $moved = @()
    $index = 0
    foreach ($entry in $intent.items) {
        $source = Assert-StatePath (Join-Path $runDirectory $entry.relative)
        $destination = Assert-StatePath (Join-Path $target $entry.relative)
        $moveReceiptPath = $stem + '.move-' + $index + '.json'
        if (Test-Path -LiteralPath $source) {
            if (Test-Path -LiteralPath $destination) { throw 'destination already exists' }
            if (Test-Path -LiteralPath $moveReceiptPath) { throw 'move receipt exists but source is present' }
            Assert-StateManifest $source $entry.manifest
            $parent = Assert-StatePath (Split-Path $destination -Parent)
            New-Item -ItemType Directory -Force -Path $parent | Out-Null
            $null = Assert-StatePath $destination
            Move-Item -LiteralPath $source -Destination $destination
        }
        if (Test-Path -LiteralPath $source) { throw ("move left the source in place: " + $entry.relative) }
        if (-not (Test-Path -LiteralPath $destination)) { throw ("move lost the item: " + $entry.relative) }
        Assert-StateManifest $destination $entry.manifest
        $moveReceipt = [ordered]@{ schema = 'FRANKIE_CODE_BOUND_STATE_MOVE_V1'; intent_sha256 = $intentHash; item = $entry }
        if (Test-Path -LiteralPath $moveReceiptPath) {
            $retained = Get-Content -LiteralPath (Assert-StatePath $moveReceiptPath) -Encoding UTF8 -Raw | ConvertFrom-Json
            if (($retained | ConvertTo-Json -Depth 20 -Compress) -cne ($moveReceipt | ConvertTo-Json -Depth 20 -Compress)) {
                throw 'move receipt differs from intent'
            }
        } else { Write-StateJson $moveReceiptPath $moveReceipt }
        $moved += $entry
        $index += 1
        Write-Output ("  preserved: " + $entry.relative)
    }
    $receipt = [ordered]@{
        schema              = 'FRANKIE_CODE_BOUND_STATE_SUPERSEDED_V1'
        day                 = $Day
        run_id              = $cfg.run_id
        run_directory       = $runDirectory
        stored_boss_commit  = $intent.stored_boss_commit
        current_boss_commit = $head
        stale               = ($intent.stored_boss_commit -ne 'absent' -and $intent.stored_boss_commit -ne $head)
        superseded_root     = $(if ($moved.Count -gt 0) { $target } else { $null })
        kept                = @('host-instance.c15.json', 'native-host-runtime.json')
        moved               = $moved
        at                  = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        intent_path         = $IntentPath
        intent_sha256       = $intentHash
    }
    Write-StateJson $receiptPath $receipt
    Write-Output ("receipt: " + $receiptPath)
    Write-Output ('RECEIPT ' + ($receipt | ConvertTo-Json -Depth 20 -Compress))
}

foreach ($required in 'Day', 'RunRoot', 'ToolsRoot', 'Python') {
    $value = Get-Variable -Name $required -ValueOnly -ErrorAction SilentlyContinue
    if (-not $value -or $value -like 'HOST_*') { throw "$required was not supplied by ssm_run_ps1.py --set (value: '$value')" }
}
if (-not (Get-Variable CycleIndex -ErrorAction SilentlyContinue)) { $CycleIndex = '00' }
if ($CycleIndex -notmatch '^\d{2}$') { throw "CycleIndex must be two digits (value: '$CycleIndex')" }
if ($Day -notmatch '^\d{8}$') { throw 'Day must be an eight-digit trading date' }
if ($ToolsRoot -match "[\x27\x22\r\n]") { throw 'ToolsRoot carries a quote or newline' }
$dayDirectory = Join-Path $RunRoot $Day
$dayDirectory = Assert-StatePath $dayDirectory
$cfgPath = Join-Path $dayDirectory 'actual-host-configuration.json'
$null = Assert-StatePath $cfgPath
if (-not (Test-Path -LiteralPath $cfgPath)) { throw "no run configuration for $Day at $cfgPath" }
$cfg = Get-Content -LiteralPath $cfgPath -Encoding UTF8 -Raw | ConvertFrom-Json
$runDirectory = $cfg.run_directory
if (-not $runDirectory -or -not [IO.Path]::IsPathRooted($runDirectory)) { throw 'run_directory must be absolute' }
$runDirectory = Assert-StatePath $runDirectory
if ((Test-StateSame $dayDirectory $runDirectory) -or (Test-StateWithin $dayDirectory $runDirectory)) { throw 'day evidence directory must be outside the run' }
if (-not $runDirectory -or -not (Test-Path $runDirectory)) { throw "run_directory absent: $runDirectory" }
# run_directory is interpolated into a raw Python literal below; a quote or newline would end it.
if ($runDirectory -match "[\x27\x22\r\n]") { throw 'refusing: run_directory carries a quote or newline' }
$null = Assert-StatePath $ToolsRoot
$null = Assert-StatePath (Join-Path $runDirectory 'host-instance.c15.json')
$git = (Get-Command git -ErrorAction Stop).Source
$head = (& $git -C $ToolsRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $head -notmatch '^[0-9a-f]{40}$') { throw 'could not resolve tools HEAD' }
if ($head -ne $cfg.host_runtime.boss_commit) { throw ("refusing: tools HEAD " + $head + " is not the configuration's boss_commit " + $cfg.host_runtime.boss_commit) }
if (-not (Test-Path (Join-Path $runDirectory 'host-instance.c15.json'))) { throw 'refusing: host-instance.c15.json absent; the delivered readiness is bound to it' }

$lockPath = Assert-StatePath (Join-Path $dayDirectory 'code-bound-state.lock')
$stateLock = [IO.File]::Open($lockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
try {
Assert-RunnerIdle
Assert-ForeignStateIntents 'FRANKIE_CODE_BOUND_STATE_INTENT_V1'
# Recovery precedes identity reads: interruption may have archived both identities.
$unfinished = @()
foreach ($file in @(Get-ChildItem -LiteralPath $dayDirectory -Filter 'superseded-code-bound-state-*.intent.json' -File)) {
    $null = Assert-StatePath $file.FullName
    $prior = Get-Content -LiteralPath $file.FullName -Encoding UTF8 -Raw | ConvertFrom-Json
    if (-not (Test-StateSame $prior.run_directory $runDirectory)) { continue }
    $completion = $file.FullName.Substring(0, $file.FullName.Length - '.intent.json'.Length) + '.json'
    $null = Assert-StatePath $completion
    if (Test-Path -LiteralPath $completion) {
        $done = Get-Content -LiteralPath $completion -Encoding UTF8 -Raw | ConvertFrom-Json
        if ($done.schema -ne 'FRANKIE_CODE_BOUND_STATE_SUPERSEDED_V1' -or
            -not (Test-StateSame $done.intent_path $file.FullName) -or $done.intent_sha256 -cne (Get-StateHash $file.FullName)) {
            throw 'completion receipt does not bind the retained intent'
        }
    } else { $unfinished += $file.FullName }
}
if ($unfinished.Count -gt 1) { throw 'multiple unfinished preservation intents require reconciliation' }
if ($unfinished.Count -eq 1) { Complete-StateIntent $unfinished[0]; return }

foreach ($identityRelative in @('host-identity.c15.json', 'execution/execution-identity.c15.json')) {
    $null = Assert-StatePath (Join-Path $runDirectory $identityRelative)
}
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
if ($LASTEXITCODE -ne 0 -or $identities.Count -ne 2) { throw ("could not read the identity records: " + ($identities -join ' | ')) }
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
        Get-ChildItem -LiteralPath (Assert-StatePath $cycle) -Filter 'host-ready-*.c15.json' | ForEach-Object { $candidates += ($cycleRelative + '/' + $_.Name) }
    }
    # Catch-all for an unenumerated record carrying the OLD commit literal, scoped to this run's root,
    # the execution root and THIS cycle only: another cycle's completion.c15.json carries boss_commit
    # lawfully and must stay. Kept records and chained journals (genesis/append-*) are never moved;
    # reparse points are never followed; nothing outside the resolved run root is touched.
    $root = Assert-StatePath $runDirectory
    $reparse = [IO.FileAttributes]::ReparsePoint
    foreach ($scanRoot in @($runDirectory, (Join-Path $runDirectory 'execution'), $cycle)) {
        $null = Assert-StatePath $scanRoot
        if (-not (Test-Path -LiteralPath $scanRoot)) { continue }
        Get-ChildItem -LiteralPath $scanRoot -File -Filter '*.c15.json' | Where-Object { -not ($_.Attributes -band $reparse) } | ForEach-Object {
            if (-not (Test-StateWithin $_.FullName $root)) { throw 'scan escaped run directory' }
            $name = $_.Name
            if ($name -eq 'host-instance.c15.json' -or $name -like 'verified-*' -or $name -eq 'genesis.c15.json' -or $name -like 'append-*') { return }
            $relative = $_.FullName.Substring($root.Length).TrimStart('\', '/').Replace('\', '/')
            if ($candidates -notcontains $relative) {
                if (Select-String -LiteralPath $_.FullName -SimpleMatch $stored -Quiet) {
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


$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ') + '-' + [Guid]::NewGuid().ToString('N')
$runName = Split-Path $runDirectory -Leaf
$target = Join-Path (Join-Path (Split-Path $runDirectory -Parent) 'superseded') ($runName + '-' + $stamp + '-code-' + $stored)
$target = Assert-StatePath $target
if ($target -eq $runDirectory -or (Test-StateWithin $target $runDirectory)) { throw 'archive must be outside run directory' }
if (Test-Path -LiteralPath $target) { throw 'archive destination already exists' }
$plan = @()
foreach ($relative in $candidates) {
    $source = Assert-StatePath (Join-Path $runDirectory $relative)
    if (-not (Test-StateWithin $source $runDirectory)) { throw 'candidate escaped run directory' }
    if (-not (Test-Path -LiteralPath $source)) { Write-Output ("  absent, skipped: " + $relative); continue }
    $destination = Assert-StatePath (Join-Path $target $relative)
    if (-not (Test-StateWithin $destination $target)) { throw 'candidate destination escaped archive' }
    $item = Get-Item -LiteralPath $source -Force
    $mtime = $item.LastWriteTimeUtc.ToString('o')
    $manifest = @(Get-StateManifest $source)
    $rootEntry = @($manifest | Where-Object { $_.relative -eq '.' })[0]
    $plan += [ordered]@{ relative = $relative; destination = $destination; sha256 = $rootEntry.sha256;
        bytes = $rootEntry.bytes; mtime_utc = $mtime; manifest = $manifest }
}
$intentPath = Join-Path $dayDirectory ('superseded-code-bound-state-' + $stamp + '.intent.json')
$intent = [ordered]@{
    schema = 'FRANKIE_CODE_BOUND_STATE_INTENT_V1'
    day = $Day
    run_id = $cfg.run_id
    run_directory = $runDirectory
    cycle_index = $CycleIndex
    stored_boss_commit = $stored
    current_boss_commit = $head
    superseded_root = $target
    items = @($plan)
}
Write-StateJson $intentPath $intent
Complete-StateIntent $intentPath
} finally { $stateLock.Dispose() }
