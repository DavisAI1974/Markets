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
# Durable preservation: complete hashed intent before moves, shared helper lock,
# per-move witnesses and replay before source absence checks. Completion/acceptance
# and process inventory gates fail closed. Existing evidence is never overwritten.
$ErrorActionPreference = 'Stop'

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

$stateKind = 'cycle'
$intentSchema = 'FRANKIE_CYCLE_STATE_INTENT_V1'
$moveSchema = 'FRANKIE_CYCLE_STATE_MOVE_V1'
$completionSchema = 'FRANKIE_CYCLE_STATE_SUPERSEDED_V1'
$receiptPrefix = 'cycle-state-superseded-'
$responseNames = @()
$kept = @('cycles.sqlite (stages superseded by the declared cycle supersede)', 'lessons.sqlite', 'host-instance.c15.json',
    'native-host-runtime.json', 'verified-*', 'host-prefix')

function Assert-ScopedGates([string[]]$CycleLocations) {
    # An unavailable process inventory cannot establish an idle runner.
    $inventory = @(Get-CimInstance Win32_Process -ErrorAction Stop)
    if ($inventory.Count -eq 0) { throw 'refusing: process inventory is empty; runner absence is unevaluable' }
    foreach ($process in $inventory) {
        if ($process.Name -isnot [string] -or [string]::IsNullOrWhiteSpace($process.Name)) {
            throw 'refusing: process inventory contains an unevaluable name'
        }
        # Include pythonw, versioned/free-threaded/debug Python names and py/pyw
        # launchers. Missing command lines cannot establish runner absence.
        if ($process.Name -match '^(?:python[^/\\]*|pyw?)(?:\.exe)?$' -and
            ($process.CommandLine -isnot [string] -or [string]::IsNullOrWhiteSpace($process.CommandLine))) {
            throw 'refusing: a Python process has an unevaluable command line'
        }
    }
    $alive = @($inventory | Where-Object { $_.CommandLine -like '*run_actual_sunday*' })
    if ($alive.Count -gt 0) { throw ("refusing: a runner process is alive (pid " + ($alive | ForEach-Object { $_.ProcessId }) + ")") }
    foreach ($location in $CycleLocations) {
        $principal = Assert-StatePath (Join-Path $location 'principal')
        $completion = Assert-StatePath (Join-Path $principal 'dipole-classroom-completion.json')
        if (Test-Path -LiteralPath $completion) { throw 'refusing: this cycle holds a Dipole classroom completion; a finished classroom is never superseded here' }
        $response = Assert-StatePath (Join-Path $principal 'session-response.json')
        if ($stateKind -eq 'cycle' -and (Test-Path -LiteralPath $response)) {
            throw 'refusing: a session-response.json is recorded for this cycle; the cycle is never superseded'
        }
    }
    $cyclesDb = Assert-StatePath (Join-Path $runDirectory 'cycles.sqlite')
    if (-not (Test-Path -LiteralPath $cyclesDb -PathType Leaf)) { throw 'refusing: the principal_output gate has no cycles.sqlite' }
    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'refusing: the principal_output gate has no interpreter' }
    # Literal here-string: no PowerShell or shell interpolation in the SQL/Python.
    $gateCode = @'
import pathlib, sqlite3, sys
with sqlite3.connect(pathlib.Path(sys.argv[1]).as_uri()+'?mode=ro', uri=True) as connection:
    print(connection.execute("select count(*) from stages where stage='principal_output' and request like ?", ('%cycle-'+sys.argv[2]+'%',)).fetchone()[0])
'@
    $accepted = (& $Python -c $gateCode $cyclesDb $CycleIndex 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $accepted -notmatch '^\d+$') { throw 'refusing: the principal_output gate could not be evaluated' }
    if ([long]$accepted -gt 0) { throw 'refusing: the coordinator retains a principal_output for this request (the runner accepted the response); not superseded here' }
    return 'checked: 0 principal_output stages for this request'
}

function Get-ScopedDestination([string]$Relative, [string]$Target) {
    if (-not $Relative -or [IO.Path]::IsPathRooted($Relative) -or $Relative.Contains('\') -or
        @($Relative.Split('/') | Where-Object { $_ -in @('', '.', '..') }).Count -gt 0) {
        throw 'invalid preservation relative path'
    }
    if ($stateKind -eq 'cycle') {
        if ($Relative -cnotin @(('execution/cycle-' + $CycleIndex), ('handoff-' + $requestSha))) {
            throw 'intent selects another cycle or unapproved evidence'
        }
        return Assert-StatePath (Join-Path $Target ($Relative.Replace('/', '__')))
    }
    $parts = $Relative.Split('/')
    $allowed = $parts.Count -eq 2 -and (
        ($parts[0] -ceq 'principal' -and ($parts[1] -cin $responseNames -or
            $parts[1] -clike 'incoming-*' -or $parts[1] -clike 'response-check-*')) -or
        $Relative -ceq 'classroom-audit/dipole-classroom-post-grade.json')
    if (-not $allowed) { throw 'intent selects request-independent or unapproved evidence' }
    return Assert-StatePath (Join-Path $Target $Relative)
}

function Complete-ScopedIntent([string]$IntentPath) {
    $IntentPath = Assert-StatePath $IntentPath
    $intent = Get-Content -LiteralPath $IntentPath -Encoding UTF8 -Raw | ConvertFrom-Json
    if ($intent.schema -cne $intentSchema -or -not (Test-StateSame $intent.run_directory $runDirectory) -or
        -not (Test-StateSame $intent.source_root $sourceRoot) -or $intent.run_id -cne $cfg.run_id -or
        $intent.day -cne $Day -or $intent.cycle_index -cne $CycleIndex -or
        $intent.reason -cne $Reason -or $intent.boss_commit -cne $cfg.host_runtime.boss_commit -or
        $intent.configuration_sha256 -cne (Get-StateHash $cfgPath)) {
        throw 'unfinished intent does not match this configuration/run/cycle/reason'
    }
    $target = Assert-StatePath $intent.superseded_root
    $archiveRoot = Assert-StatePath (Join-Path (Split-Path $runDirectory -Parent) 'superseded')
    if (-not (Test-StateWithin $target $archiveRoot) -or (Test-StateWithin $target $runDirectory) -or
        (Test-StateSame $target $runDirectory)) { throw 'intent destination escaped the sibling archive' }
    if ($intent.items -isnot [Array] -or $intent.items.Count -eq 0) { throw 'intent needs a nonempty item array' }
    $stem = $IntentPath.Substring(0, $IntentPath.Length - '.intent.json'.Length)
    $intentHash = Get-StateHash $IntentPath
    $seen = @{}
    $expectedReceipts = @{}
    $cycleLocations = @($cycle)
    $index = 0
    # Whole-transaction preflight precedes every recovery move.
    foreach ($entry in $intent.items) {
        $relative = [string]$entry.relative
        if ($seen.ContainsKey($relative)) { throw 'duplicate preservation item' }
        $seen[$relative] = $true
        $destination = Get-ScopedDestination $relative $target
        $source = Assert-StatePath (Join-Path $sourceRoot $relative)
        if (-not (Test-StateWithin $source $sourceRoot) -or -not (Test-StateWithin $destination $target) -or
            -not (Test-StateSame $entry.destination $destination)) { throw 'intent path escaped its root' }
        if ($entry.manifest -isnot [Array] -or $entry.manifest.Count -eq 0) { throw 'intent lacks a complete manifest' }
        $atSource = Test-Path -LiteralPath $source
        $atDestination = Test-Path -LiteralPath $destination
        if ($atSource -eq $atDestination) { throw 'ambiguous or missing preserved item' }
        if ($atSource) { Assert-StateManifest $source $entry.manifest }
        else { Assert-StateManifest $destination $entry.manifest }
        if ($stateKind -eq 'cycle' -and $relative -ceq ('execution/cycle-' + $CycleIndex) -and $atDestination) {
            $cycleLocations += $destination
        }
        $movePath = Assert-StatePath ($stem + '.move-' + $index + '.json')
        $expectedReceipts[$movePath] = $true
        if (Test-Path -LiteralPath $movePath) {
            if ($atSource) { throw 'move receipt exists but source remains' }
            $retained = Get-Content -LiteralPath $movePath -Encoding UTF8 -Raw | ConvertFrom-Json
            $expected = [ordered]@{ schema = $moveSchema; intent_sha256 = $intentHash; item = $entry }
            if (($retained | ConvertTo-Json -Depth 20 -Compress) -cne ($expected | ConvertTo-Json -Depth 20 -Compress)) {
                throw 'retained move receipt conflicts with intent'
            }
        }
        $index += 1
    }
    foreach ($file in @(Get-ChildItem -LiteralPath $dayDirectory -Filter ((Split-Path $stem -Leaf) + '.move-*.json') -Force)) {
        $path = Assert-StatePath $file.FullName
        if (-not $expectedReceipts.ContainsKey($path)) { throw 'unexpected move receipt outside intent' }
    }
    $gate = Assert-ScopedGates $cycleLocations
    $moved = [ordered]@{}
    $index = 0
    foreach ($entry in $intent.items) {
        $source = Assert-StatePath (Join-Path $sourceRoot $entry.relative)
        $destination = Get-ScopedDestination $entry.relative $target
        $movePath = Assert-StatePath ($stem + '.move-' + $index + '.json')
        if (Test-Path -LiteralPath $source) {
            if ((Test-Path -LiteralPath $destination) -or (Test-Path -LiteralPath $movePath)) { throw 'move destination or receipt already exists' }
            Assert-StateManifest $source $entry.manifest
            $parent = Assert-StatePath (Split-Path $destination -Parent)
            New-Item -ItemType Directory -Force -Path $parent | Out-Null
            $null = Assert-StatePath $destination
            Move-Item -LiteralPath $source -Destination $destination
        }
        if ((Test-Path -LiteralPath $source) -or -not (Test-Path -LiteralPath $destination)) { throw 'move did not preserve one destination' }
        Assert-StateManifest $destination $entry.manifest
        $moveReceipt = [ordered]@{ schema = $moveSchema; intent_sha256 = $intentHash; item = $entry }
        if (-not (Test-Path -LiteralPath $movePath)) { Write-StateJson $movePath $moveReceipt }
        $rootEntry = @($entry.manifest | Where-Object { $_.relative -ceq '.' })[0]
        $record = [ordered]@{ kind = $rootEntry.kind; bytes = $rootEntry.bytes; sha256 = $rootEntry.sha256; destination = $destination; manifest = $entry.manifest }
        if ($stateKind -eq 'cycle') {
            $files = [ordered]@{}
            foreach ($file in @($entry.manifest | Where-Object { $_.kind -ceq 'file' })) {
                $files[$file.relative] = [ordered]@{ bytes = $file.bytes; sha256 = $file.sha256 }
            }
            $record.files = $files
        }
        $moved[$entry.relative] = $record
        $index += 1
        Write-Output ('MOVED ' + $entry.relative + ' -> ' + $destination)
    }
    $receipt = [ordered]@{
        schema = $completionSchema; day = $Day; run_id = $cfg.run_id; run_directory = $runDirectory
        cycle_index = [int]$CycleIndex; request_id = $requestId; superseded_root = $target
        moved = $moved; kept = $kept; reason = $Reason; at = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        principal_output_gate = $gate; intent_path = $IntentPath; intent_sha256 = $intentHash
    }
    if ($stateKind -eq 'response') {
        $receipt.principal = Join-Path $cycle 'principal'
        $receipt.planned_receipt = $IntentPath
    }
    Write-StateJson ($stem + '.json') $receipt
    Write-Output ('RECEIPT ' + ($receipt | ConvertTo-Json -Depth 20 -Compress))
}

foreach ($required in 'Day', 'RunRoot', 'CycleIndex', 'Reason', 'Python') {
    $value = Get-Variable -Name $required -ValueOnly -ErrorAction SilentlyContinue
    if (-not $value -or $value -like 'HOST_*') { throw "$required was not supplied by ssm_run_ps1.py --set" }
}
if ($CycleIndex -notmatch '^\d{2}$') { throw 'CycleIndex must be two digits' }
if ($Day -notmatch '^\d{8}$') { throw 'Day must be an eight-digit trading date' }
if (-not [IO.Path]::IsPathRooted($RunRoot)) { throw 'RunRoot must be absolute' }
$dayDirectory = Assert-StatePath (Join-Path $RunRoot $Day)
$cfgPath = Assert-StatePath (Join-Path $dayDirectory 'actual-host-configuration.json')
$cfg = Get-Content -LiteralPath $cfgPath -Encoding UTF8 -Raw | ConvertFrom-Json
if (-not $cfg.run_id -or -not [IO.Path]::IsPathRooted([string]$cfg.run_directory) -or
    $cfg.host_runtime.boss_commit -cnotmatch '^[0-9a-f]{40}$') { throw 'complete run identity and configured commit required' }
$runDirectory = Assert-StatePath $cfg.run_directory
if (-not (Test-Path -LiteralPath $runDirectory -PathType Container)) { throw 'run directory absent' }
if ((Test-StateSame $dayDirectory $runDirectory) -or (Test-StateWithin $dayDirectory $runDirectory)) {
    throw 'day evidence directory must be outside the run'
}
$cycle = Assert-StatePath (Join-Path (Join-Path $runDirectory 'execution') ('cycle-' + $CycleIndex))
$sourceRoot = $runDirectory
if ($stateKind -eq 'response') { $sourceRoot = $cycle }
$requestId = $cfg.run_id + '-cycle-' + $CycleIndex
$hasher = [Security.Cryptography.SHA256]::Create()
try { $requestSha = ([BitConverter]::ToString($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($requestId)))).Replace('-', '').ToLowerInvariant() }
finally { $hasher.Dispose() }

$lockPath = Assert-StatePath (Join-Path $dayDirectory 'code-bound-state.lock')
$stateLock = [IO.File]::Open($lockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
try {
    Assert-ForeignStateIntents $intentSchema
    $unfinished = @()
    foreach ($file in @(Get-ChildItem -LiteralPath $dayDirectory -Filter ($receiptPrefix + '*.intent.json') -Force)) {
        $path = Assert-StatePath $file.FullName
        if ($file.PSIsContainer) { throw 'intent is not a file' }
        $prior = Get-Content -LiteralPath $path -Encoding UTF8 -Raw | ConvertFrom-Json
        if ($prior.schema -cne $intentSchema) { throw 'malformed preservation intent' }
        $completion = Assert-StatePath ($path.Substring(0, $path.Length - '.intent.json'.Length) + '.json')
        if (Test-Path -LiteralPath $completion) {
            $done = Get-Content -LiteralPath $completion -Encoding UTF8 -Raw | ConvertFrom-Json
            if ($done.schema -cne $completionSchema -or -not $done.intent_path -or
                -not (Test-StateSame $done.intent_path $path) -or $done.intent_sha256 -cne (Get-StateHash $path)) {
                throw 'completion does not bind the retained intent'
            }
        } else { $unfinished += $path }
    }
    if ($unfinished.Count -gt 1) { throw 'multiple unfinished intents require reconciliation' }
    if ($unfinished.Count -eq 1) { Complete-ScopedIntent $unfinished[0]; return }
    $gate = Assert-ScopedGates @($cycle)
    $relativeNames = @()
    if ($stateKind -eq 'response') {
        $principal = Assert-StatePath (Join-Path $cycle 'principal')
        if (-not (Test-Path -LiteralPath (Join-Path $principal 'session-response.json'))) {
            Write-Output 'NOTHING_RECORDED no session-response.json for this cycle; nothing to supersede'
            return
        }
        foreach ($name in $responseNames) {
            if (Test-Path -LiteralPath (Join-Path $principal $name)) { $relativeNames += 'principal/' + $name }
        }
        foreach ($directory in @(Get-ChildItem -LiteralPath $principal -Directory -Force |
            Where-Object { $_.Name -like 'incoming-*' -or $_.Name -like 'response-check-*' })) {
            $relativeNames += 'principal/' + $directory.Name
        }
        if (Test-Path -LiteralPath (Join-Path $cycle 'classroom-audit/dipole-classroom-post-grade.json')) {
            $relativeNames += 'classroom-audit/dipole-classroom-post-grade.json'
        }
    } else {
        foreach ($relative in @(('execution/cycle-' + $CycleIndex), ('handoff-' + $requestSha))) {
            if (Test-Path -LiteralPath (Join-Path $sourceRoot $relative)) { $relativeNames += $relative }
        }
        if ($relativeNames.Count -eq 0) { Write-Output 'NOTHING_RETAINED nothing to supersede'; return }
    }
    $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ') + '-' + [Guid]::NewGuid().ToString('N')
    $suffix = '-cycle-' + $CycleIndex
    if ($stateKind -eq 'response') { $suffix = '-principal-response-cycle-' + $CycleIndex }
    $target = Assert-StatePath (Join-Path (Join-Path (Split-Path $runDirectory -Parent) 'superseded') ((Split-Path $runDirectory -Leaf) + '-' + $stamp + $suffix))
    if (Test-Path -LiteralPath $target) { throw 'archive destination already exists' }
    $plan = @()
    foreach ($relative in $relativeNames) {
        $source = Assert-StatePath (Join-Path $sourceRoot $relative)
        if (-not (Test-StateWithin $source $sourceRoot)) { throw 'candidate escaped source root' }
        $destination = Get-ScopedDestination $relative $target
        $manifest = @(Get-StateManifest $source)
        $plan += [ordered]@{ relative = $relative; destination = $destination;
            mtime_utc = (Get-Item -LiteralPath $source -Force).LastWriteTimeUtc.ToString('o'); manifest = $manifest }
    }
    $intentPath = Join-Path $dayDirectory ($receiptPrefix + $stamp + '.intent.json')
    $intent = [ordered]@{
        schema = $intentSchema; day = $Day; run_id = $cfg.run_id; run_directory = $runDirectory
        source_root = $sourceRoot; cycle_index = $CycleIndex; reason = $Reason
        boss_commit = $cfg.host_runtime.boss_commit; configuration_sha256 = (Get-StateHash $cfgPath)
        superseded_root = $target; items = @($plan); principal_output_gate = $gate
    }
    Write-StateJson $intentPath $intent
    Complete-ScopedIntent $intentPath
} finally { $stateLock.Dispose() }
