# Make the native host's tools checkout byte-identical to the committed tree (2026-09-20).
#
# Why: the runner hashes SOURCE BYTES into identities the retained Granite observer pins
# (*_parser_code_hash over granite_context*, granite_parser, c15_journal, the stacked route and
# codec; run_actual_sunday.py hashes every .py under frankie_boss and refrag). The observer runs
# on Linux (LF). This host is a Windows checkout with core.autocrlf=true, so git rewrote those
# sources to CRLF on checkout and the host's identity_hash differed from the observer's pins:
# line 843 'trusted host service pins differ' refused pipeline run 35512638774 after a full
# re-preparation. Reproduced byte for byte off the host: the CRLF-converted sources hash to the
# host's parser_code_hash fcd6702a... and identity 6993d307...; the LF sources hash to the pins.
#
# What this does: sets core.autocrlf=false for THIS checkout only and rewrites the working tree
# from the index (git checkout-index --force --all), which restores every tracked file to its
# committed bytes. Nothing is deleted, no commit moves, no path is hand-edited. Refuses on a
# dirty tree before and after. Counts the frankie_boss/refrag .py files carrying a CR byte before
# and after (the three committed with CRLF stay as committed) and writes a receipt into the day
# directory. Starts, stops and dispatches nothing. .gitattributes (-text on those globs) makes
# the discipline durable once the host is advanced to a commit that carries it.
#
# $ToolsRoot, $RunRoot and $Day arrive from ssm_run_ps1.py --set; no path literal here.
$ErrorActionPreference = 'Stop'
foreach ($required in 'ToolsRoot', 'RunRoot', 'Day') {
    $value = Get-Variable -Name $required -ValueOnly -ErrorAction SilentlyContinue
    if (-not $value -or $value -like 'HOST_*') { throw "$required was not supplied by ssm_run_ps1.py --set (value: '$value')" }
}
$git = (Get-Command git -ErrorAction Stop).Source
if (-not (Test-Path $ToolsRoot)) { throw "tools checkout missing: $ToolsRoot" }
$dayDirectory = Join-Path $RunRoot $Day
if (-not (Test-Path $dayDirectory)) { throw "day directory missing: $dayDirectory" }
$dirty = & $git -C $ToolsRoot status --porcelain
if ($dirty) { throw ("refusing: tools checkout is dirty:`n" + ($dirty -join "`n")) }
$head = (& $git -C $ToolsRoot rev-parse HEAD).Trim()
$autocrlfBefore = (& $git -C $ToolsRoot config --get core.autocrlf 2>$null)
if (-not $autocrlfBefore) { $autocrlfBefore = (& $git -C $ToolsRoot config --global --get core.autocrlf 2>$null) }
if (-not $autocrlfBefore) { $autocrlfBefore = 'unset' }

function Count-CR([string]$root) {
    $hits = @()
    foreach ($sub in 'research\kalshi\frankie_boss', 'research\refrag') {
        $dir = Join-Path $root $sub
        if (-not (Test-Path $dir)) { continue }
        Get-ChildItem $dir -Recurse -File -Filter '*.py' | ForEach-Object {
            if ([IO.File]::ReadAllBytes($_.FullName) -contains 13) { $hits += $_.FullName.Substring($root.Length).TrimStart('\', '/').Replace('\', '/') }
        }
    }
    return $hits
}
$before = Count-CR $ToolsRoot
$probeFile = 'research/kalshi/frankie_boss/granite_context_stacked_route.py'
Write-Output ("HEAD=" + $head + "  core.autocrlf(before)=" + $autocrlfBefore + "  .py files carrying CR (before)=" + $before.Count)
# Which mechanism converts: every origin of the two settings, the attribute set, and the eol view.
Write-Output "--- diagnostics before ---"
& $git -C $ToolsRoot --version
& $git -C $ToolsRoot config --show-origin --get-all core.autocrlf 2>$null | ForEach-Object { "  core.autocrlf: $_" }
& $git -C $ToolsRoot config --show-origin --get-all core.eol 2>$null | ForEach-Object { "  core.eol: $_" }
& $git -C $ToolsRoot config --show-origin --get-all core.attributesFile 2>$null | ForEach-Object { "  core.attributesFile: $_" }
& $git -C $ToolsRoot check-attr -a -- $probeFile | ForEach-Object { "  attr: $_" }
& $git -C $ToolsRoot ls-files --eol -- $probeFile | ForEach-Object { "  eol: $_" }

# 2026-09-20 run 35514364576: checkout-index --force --all rewrote nothing (391 -> 391), so the
# re-checkout is done the documented way: drop the two roots from the index and restore them from
# HEAD with the corrected settings. The tree was verified clean above, so reset --hard loses nothing.
& $git -C $ToolsRoot config core.autocrlf false
if ($LASTEXITCODE -ne 0) { throw 'could not set core.autocrlf=false on the checkout' }
& $git -C $ToolsRoot config core.eol lf
if ($LASTEXITCODE -ne 0) { throw 'could not set core.eol=lf on the checkout' }
& $git -C $ToolsRoot rm --cached -r -q -- research/kalshi/frankie_boss research/refrag
if ($LASTEXITCODE -ne 0) { throw 'git rm --cached failed; nothing on disk was changed (re-run is safe)' }
& $git -C $ToolsRoot reset -q --hard HEAD
if ($LASTEXITCODE -ne 0) { throw 'git reset --hard HEAD failed; re-run is safe, the index restores from HEAD' }
$autocrlfAfter = (& $git -C $ToolsRoot config --get core.autocrlf).Trim()
$after = Count-CR $ToolsRoot
Write-Output "--- diagnostics after ---"
& $git -C $ToolsRoot ls-files --eol -- $probeFile | ForEach-Object { "  eol: $_" }
$dirtyAfter = & $git -C $ToolsRoot status --porcelain
if ($dirtyAfter) { throw ("working tree not clean after normalisation:`n" + ($dirtyAfter -join "`n")) }
# The committed-CRLF files are expected to keep their CR; every other hit must be gone.
$committedCRLF = @(& $git -C $ToolsRoot grep -I -l -P '\r' HEAD -- 'research/kalshi/frankie_boss/*.py' 'research/refrag/*.py' 2>$null | ForEach-Object { $_ -replace '^HEAD:', '' })
Write-Output ("core.autocrlf(after)=" + $autocrlfAfter + "  core.eol(after)=lf  .py files carrying CR (after)=" + $after.Count + "  committed with CRLF=" + $committedCRLF.Count)
$unexpected = @($after | Where-Object { $committedCRLF -notcontains $_ })
if ($unexpected.Count -gt 0) { throw ("files still carry CR that the commit does not: " + ($unexpected -join ', ')) }
# The one hash that refused: the stacked route source must now equal its committed blob.
$blob = (& $git -C $ToolsRoot rev-parse ("HEAD:" + $probeFile)).Trim()
$worktree = (& $git -C $ToolsRoot hash-object (Join-Path $ToolsRoot $probeFile)).Trim()
if ($blob -ne $worktree) { throw ("working-tree bytes of " + $probeFile + " still differ from the committed blob") }
$receipt = [ordered]@{
    schema           = 'FRANKIE_HOST_EOL_NORMALIZED_V1'
    tools            = $ToolsRoot
    head             = $head
    autocrlf_before  = $autocrlfBefore
    autocrlf_after   = $autocrlfAfter
    core_eol_after   = 'lf'
    cr_files_before  = $before.Count
    cr_files_after   = $after.Count
    committed_crlf   = $committedCRLF
    rewritten        = @($before | Where-Object { $after -notcontains $_ })
    probe_file       = $probeFile
    probe_blob_equal = $true
    at               = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
}
$receiptPath = Join-Path $dayDirectory ('host-eol-normalized-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ') + '.json')
Set-Content -Path $receiptPath -Value ($receipt | ConvertTo-Json -Depth 4) -NoNewline -Encoding UTF8
Write-Output ("receipt: " + $receiptPath)
Write-Output ('RECEIPT ' + ($receipt | ConvertTo-Json -Depth 4 -Compress))
