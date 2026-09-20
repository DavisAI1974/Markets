# Rebuild the two-cycle Sunday prefix batch on the native host's normalized tools checkout
# (2026-09-20). Read frankie_host_normalize_eol.ps1 first.
#
# Why: the batch retained on the host (remaining-prefix-binding.json, prefix-01-packet-seed.json,
# prefix-batch-02.json) was built on 2026-09-19 on the CRLF checkout, and it pins the sha256 of the
# builder, the copier, sunday_native_runtime.py and context_session.py as they were then read. Those
# sources are committed LF; after the normalization the checkout's bytes hash to the committed
# values, so run_actual_sunday.encoding_options refuses cycle 1 ('prefix seed differs from verified
# current snapshot/context selection') and the builder itself refuses to reuse the old seed sidecar
# and binding. The snapshots are data and are unaffected; only the code pins are stale.
#
# What this does: (1) compares the binding's code pins to the checkout's bytes and stops if nothing
# is stale; (2) MOVES (never deletes) the batch's code-pinned files into
# <prefixes parent>/superseded/<prefixes name>-<stamp>-prefix-batch/ with their sha256 recorded;
# prefix-00 (retained from the first run) is never touched; (3) runs the gold-standard builder,
# unchanged, exactly as day_schedule_prefixes.ps1 runs it; (4) rewrites ONLY the sha256 (and bytes,
# when present) of host_runtime.prefix_manifest in the day's configuration, keeping a dated backup,
# because the runner verifies the manifest by that witness; (5) writes one receipt into the day
# directory. Starts, stops and dispatches nothing. Re-runnable: a second run finds nothing stale.
#
# $Day, $RunRoot, $ToolsRoot and $Python arrive from ssm_run_ps1.py --set; no path literal here.
$ErrorActionPreference = 'Stop'
foreach ($required in 'Day', 'RunRoot', 'ToolsRoot', 'Python') {
    $value = Get-Variable -Name $required -ValueOnly -ErrorAction SilentlyContinue
    if (-not $value -or $value -like 'HOST_*') { throw "$required was not supplied by ssm_run_ps1.py --set (value: '$value')" }
}
if (-not (Get-Variable CycleLimit -ErrorAction SilentlyContinue)) { $CycleLimit = 2 }
if ([int]$CycleLimit -ne 2) { throw 'this rebuild covers the two-cycle batch only (prefix-batch-02.json)' }
$dayDirectory = Join-Path $RunRoot $Day
$cfgPath = Join-Path $dayDirectory 'actual-host-configuration.json'
if (-not (Test-Path $cfgPath)) { throw "no run configuration for $Day at $cfgPath" }
$raw = Get-Content $cfgPath -Raw
$cfg = $raw | ConvertFrom-Json
$prefixes = $cfg.host_runtime.prefixes_directory
if (-not $prefixes -or -not (Test-Path $prefixes)) { throw "prefixes_directory absent: $prefixes" }
$manifestPath = $cfg.host_runtime.prefix_manifest.path
$oldManifestSha = $cfg.host_runtime.prefix_manifest.sha256
if (-not $manifestPath -or -not $oldManifestSha) { throw 'configuration declares no prefix_manifest witness' }
if ((Split-Path $manifestPath -Leaf) -ne 'prefix-batch-02.json') { throw ("configuration pins " + $manifestPath + ", not the two-cycle batch") }
if ((Resolve-Path (Split-Path $manifestPath -Parent)).Path -ne (Resolve-Path $prefixes).Path) { throw 'prefix manifest is not inside prefixes_directory' }
$git = (Get-Command git -ErrorAction Stop).Source
$head = (& $git -C $ToolsRoot rev-parse HEAD).Trim()
if ($head -ne $cfg.host_runtime.boss_commit) { throw ("refusing: tools HEAD " + $head + " is not the configuration's boss_commit " + $cfg.host_runtime.boss_commit) }
$dirty = & $git -C $ToolsRoot status --porcelain -- research/kalshi/frankie_boss research/refrag
if ($dirty) { throw ("refusing: tools checkout is dirty under the hashed roots:`n" + ($dirty -join "`n")) }
$code = Join-Path $ToolsRoot 'research\kalshi\frankie_boss'
function Sha([string]$path) { return (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLower() }

# 1. Stale? The binding pins the code that selected the seeds; compare to the checkout's bytes.
$bindingPath = Join-Path $prefixes 'remaining-prefix-binding.json'
if (-not (Test-Path $bindingPath)) { throw ("no batch binding at " + $bindingPath + "; nothing to judge by") }
$binding = Get-Content $bindingPath -Raw | ConvertFrom-Json
$pins = @(
    @{ name = 'script_sha256'; pinned = $binding.script_sha256; file = 'operations\build_remaining_sunday_prefixes.py' },
    @{ name = 'copier_sha256'; pinned = $binding.copier_sha256; file = 'journal_prefix_snapshot.py' },
    @{ name = 'context_selection.runtime_code_sha256'; pinned = $binding.context_selection.runtime_code_sha256; file = 'sunday_native_runtime.py' },
    @{ name = 'context_selection.selection_code_sha256'; pinned = $binding.context_selection.selection_code_sha256; file = 'context_session.py' })
if ($binding.compact_copier_sha256) {
    $pins += @{ name = 'compact_copier_sha256'; pinned = $binding.compact_copier_sha256; file = 'compact_journal_snapshot.py' }
    $pins += @{ name = 'full_reader_sha256'; pinned = $binding.full_reader_sha256; file = 'frankie_journal_reader.py' }
}
$stale = @()
foreach ($pin in $pins) {
    $current = Sha (Join-Path $code $pin.file)
    $state = if ($current -eq $pin.pinned) { 'equal' } else { 'STALE' }
    Write-Output ("  " + $pin.name + ": pinned=" + $pin.pinned + " current=" + $current + " " + $state)
    if ($state -eq 'STALE') { $stale += $pin.name }
}
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$moved = @()
$target = $null
$builderExit = $null
$newManifestSha = $null
$backup = $null
if ($stale.Count -eq 0) {
    Write-Output 'the batch binding matches the checkout; nothing is stale and nothing moves'
} else {
    # 2. Move the code-pinned batch files aside. prefix-00-* is the first run's retained prefix: kept.
    $candidates = @('remaining-prefix-binding.json', 'prefix-batch-02.json', 'remaining-prefix-progress.jsonl')
    for ($index = 1; $index -lt [int]$CycleLimit; $index++) {
        $tag = 'prefix-' + $index.ToString('00')
        $candidates += @(($tag + '.sqlite'), ($tag + '-receipt.json'), ($tag + '-witness.json'), ($tag + '-packet-seed.json'))
    }
    $leaf = Split-Path $prefixes -Leaf
    $target = Join-Path (Join-Path (Split-Path $prefixes -Parent) 'superseded') ($leaf + '-' + $stamp + '-prefix-batch')
    foreach ($name in $candidates) {
        if ($name -like 'prefix-00*') { throw 'refusing: prefix-00 is never a candidate' }
        $source = Join-Path $prefixes $name
        if (-not (Test-Path $source)) { Write-Output ("  absent, skipped: " + $name); continue }
        $partials = @(Get-ChildItem $prefixes -File -Filter ($name + '.partial-*'))
        if ($partials.Count -gt 0) { throw ("refusing: partial file(s) beside " + $name + "; inspect before rebuild") }
        $destination = Join-Path $target $name
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        $item = Get-Item $source
        $digest = Sha $source
        Move-Item -LiteralPath $source -Destination $destination
        if (Test-Path $source) { throw ("move left the source in place: " + $name) }
        if (-not (Test-Path $destination)) { throw ("move lost the item: " + $name) }
        $moved += [ordered]@{ name = $name; destination = $destination; sha256 = $digest; bytes = $item.Length; mtime_utc = $item.LastWriteTimeUtc.ToString('s') + 'Z' }
        Write-Output ("  moved: " + $name + "  sha256=" + $digest)
    }
    # 3. The gold-standard builder, unchanged, invoked exactly as day_schedule_prefixes.ps1 invokes it.
    $tool = Join-Path $ToolsRoot 'research\kalshi\frankie_boss\operations\build_remaining_sunday_prefixes.py'
    $log = Join-Path $dayDirectory ('day-rebuild-prefixes-' + $stamp + '.log')
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:PYTHONPATH = $ToolsRoot
    Push-Location $ToolsRoot
    try {
        & cmd.exe /c "`"$Python`" `"$tool`" --configuration `"$cfgPath`" --cycles $CycleLimit > `"$log`" 2>&1"
        $builderExit = $LASTEXITCODE
    } finally { Pop-Location }
    if (Test-Path $log) {
        Get-Content $log -Tail 40 | ForEach-Object { $_.ToString().Substring(0, [Math]::Min(400, $_.ToString().Length)) }
    }
    if ($builderExit -ne 0) { throw "build_remaining_sunday_prefixes exited $builderExit for $Day; the moved batch is under $target" }
    if (-not (Test-Path $manifestPath)) { throw "the builder left no prefix-batch-02.json at $manifestPath" }
    $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
    if (@($manifest.witnesses).Count -ne [int]$manifest.prefixes -or [int]$manifest.prefixes -ne [int]$CycleLimit) {
        throw ("rebuilt manifest disagrees with the request: witnesses=" + @($manifest.witnesses).Count + " prefixes=" + $manifest.prefixes)
    }
    $rebuilt = Get-Content $bindingPath -Raw | ConvertFrom-Json
    foreach ($pin in $pins) {
        $value = if ($pin.name -like 'context_selection.*') { $rebuilt.context_selection.($pin.name.Substring(18)) } else { $rebuilt.($pin.name) }
        if ($value -ne (Sha (Join-Path $code $pin.file))) { throw ("rebuilt binding still differs from the checkout at " + $pin.name) }
    }
    # 4. The runner verifies the manifest by the configuration's witness: rewrite only that witness.
    $newManifestSha = Sha $manifestPath
    $newBytes = (Get-Item $manifestPath).Length
    $backup = $cfgPath + '.before-prefix-rebuild-' + $stamp + '.json'
    Set-Content -Path $backup -Value $raw -NoNewline -Encoding UTF8
    $object = [regex]::Match($raw, '"prefix_manifest"\s*:\s*\{[^{}]*\}')
    if (-not $object.Success -or ([regex]::Matches($raw, '"prefix_manifest"\s*:')).Count -ne 1) { throw 'prefix_manifest witness not found exactly once in the configuration' }
    $witness = $object.Value
    $shaPattern = '"sha256"\s*:\s*"' + [regex]::Escape($oldManifestSha) + '"'
    if (([regex]::Matches($witness, $shaPattern)).Count -ne 1) { throw 'prefix_manifest sha256 not found exactly once inside the witness' }
    $updatedWitness = [regex]::Replace($witness, $shaPattern, '"sha256": "' + $newManifestSha + '"', 1)
    if ($null -ne $cfg.host_runtime.prefix_manifest.bytes) {
        $bytesPattern = '"bytes"\s*:\s*' + [int64]$cfg.host_runtime.prefix_manifest.bytes + '(?=\s*[,}])'
        if (([regex]::Matches($updatedWitness, $bytesPattern)).Count -ne 1) { throw 'prefix_manifest bytes not found exactly once inside the witness' }
        $updatedWitness = [regex]::Replace($updatedWitness, $bytesPattern, '"bytes": ' + $newBytes, 1)
    }
    $updated = $raw.Substring(0, $object.Index) + $updatedWitness + $raw.Substring($object.Index + $object.Length)
    Set-Content -Path $cfgPath -Value $updated -NoNewline -Encoding UTF8
    $check = (Get-Content $cfgPath -Raw | ConvertFrom-Json).host_runtime.prefix_manifest
    if ($check.sha256 -ne $newManifestSha -or $check.path -ne $manifestPath) { throw 'prefix_manifest witness did not update' }
    if ($null -ne $cfg.host_runtime.prefix_manifest.bytes -and [int64]$check.bytes -ne $newBytes) { throw 'prefix_manifest bytes did not update' }
}
$receipt = [ordered]@{
    schema               = 'FRANKIE_PREFIX_BATCH_REBUILT_V1'
    day                  = $Day
    run_id               = $cfg.run_id
    tools_head           = $head
    prefixes_directory   = $prefixes
    manifest             = $manifestPath
    stale_pins           = $stale
    superseded_root      = $target
    kept                 = @('prefix-00-witness.json and every prefix-00-* file')
    moved                = $moved
    builder_exit         = $builderExit
    manifest_sha256_before = $oldManifestSha
    manifest_sha256_after  = $(if ($newManifestSha) { $newManifestSha } else { $oldManifestSha })
    configuration_backup = $backup
    at                   = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
}
$receiptPath = Join-Path $dayDirectory ('prefix-batch-rebuilt-' + $stamp + '.json')
Set-Content -Path $receiptPath -Value ($receipt | ConvertTo-Json -Depth 6) -NoNewline -Encoding UTF8
Write-Output ("receipt: " + $receiptPath)
Write-Output ('RECEIPT ' + ($receipt | ConvertTo-Json -Depth 6 -Compress))
