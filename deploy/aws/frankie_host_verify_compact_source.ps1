$ErrorActionPreference = 'Stop'
# Prove on the real Sunday data that the compact journal is authoritative for source verification:
# hide the restored raw journal, run source() + prefix() for all 19 cycles through the compact-source
# host (no model, no training, no service), then put the raw journal back. Nothing result-bearing.
$git = 'C:\Program Files\Git\cmd\git.exe'
& $git -C C:\tools\Markets fetch -q --depth 1 origin ccode/frankie-lawful-recovery-review-20260915
& $git -C C:\tools\Markets checkout -q --detach FETCH_HEAD
Write-Output ("TOOLS_HEAD=" + (& $git -C C:\tools\Markets rev-parse HEAD))
$py = 'E:\Codex\Frankie-BOSS-20260915\actual-host-python\Scripts\python.exe'
$tool = 'C:\tools\Markets\research\kalshi\frankie_boss\operations\run_actual_sunday_compact_source.py'
$config = 'E:\Codex\Frankie-BOSS-20260915\sunday-launch-20260915\actual-host-final-configuration.json'
$raw = 'E:\Codex\Frankie-BOSS-20260915\source-recovery-resume-20260915\source.sqlite'
$hidden = $raw + '.hidden-for-compact-proof'
$out = 'E:\bench\compact-source-verify-scratch'
New-Item -ItemType Directory -Force E:\bench | Out-Null
if (Test-Path $out) { Remove-Item -Recurse -Force $out }
$env:PYTHONDONTWRITEBYTECODE = '1'
Rename-Item $raw $hidden
try {
    Write-Output ("RAW_PRESENT_DURING_RUN=" + (Test-Path $raw))
    Push-Location E:\Codex\Frankie-BOSS-20260915\sunday-launch-20260915\Markets
    & $py $tool --configuration $config --verify-source-only --run-directory $out --tools-root C:\tools\Markets 2>&1 | ForEach-Object { $_.ToString().Substring(0, [Math]::Min(400, $_.ToString().Length)) }
    $code = $LASTEXITCODE
    Pop-Location
    Write-Output "VERIFY_EXIT=$code"
} finally {
    Rename-Item $hidden $raw
    Write-Output ("RAW_RESTORED=" + (Test-Path $raw))
}
if ($code -ne 0) { throw "compact source verification failed with exit $code" }
Get-Content "$out\compact-source-verification.json" -Raw | ConvertFrom-Json | Select-Object source_seconds, total_seconds | Format-List | Out-String
