$ErrorActionPreference = 'Stop'
# Disposable native learner step, 8 then 16 intra-op threads, fresh checkpoint each, on scratch clones of the
# restored failed run. No Granite, no principal, no coordinator, no production state. Results land in E:\bench.
$py = 'E:\Codex\Frankie-BOSS-20260915\actual-host-python\Scripts\python.exe'
$repo = 'E:\Codex\Frankie-BOSS-20260915\sunday-launch-20260915\Markets'
$harness = 'C:\tools\Markets\research\kalshi\frankie_boss\operations\benchmark_native_learner_direct.py'
$source = 'E:\Codex\Frankie-BOSS-20260915\actual-feedback-run'
$config = 'E:\Codex\Frankie-BOSS-20260915\sunday-launch-20260915\actual-host-final-configuration.json'
New-Item -ItemType Directory -Force E:\bench | Out-Null
$env:PYTHONDONTWRITEBYTECODE = '1'
foreach ($threads in @(8, 16)) {
    $clone = "E:\bench\bench-run-${threads}t"
    if (Test-Path $clone) { Remove-Item -Recurse -Force $clone }
    Copy-Item -Recurse $source $clone
    Remove-Item "$clone\host-identity.c15.json"
    $cfg = Get-Content $config -Raw | ConvertFrom-Json
    $cfg.run_directory = $clone
    $cfgPath = "E:\bench\bench_config_${threads}t.json"
    $cfg | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 $cfgPath
    Write-Output "=== threads=$threads start $(Get-Date -Format s)"
    Push-Location $repo
    & $py $harness --repository . --configuration $cfgPath --threads $threads --log "E:\bench\direct_${threads}t.jsonl" 2>&1 | Tee-Object -FilePath "E:\bench\direct_${threads}t.stdout" | Select-String -Pattern 'FRANKIE_NATIVE_LEARNER_DIRECT_BENCHMARK_V1|driver_failed|learner_step' | ForEach-Object { $_.Line.Substring(0, [Math]::Min(400, $_.Line.Length)) }
    $code = $LASTEXITCODE
    Pop-Location
    Write-Output "=== threads=$threads exit=$code end $(Get-Date -Format s)"
    # Header-only SQLite residue from read-only opens: remove so the next invocation's lineage check is not tripped.
    foreach ($d in @('source-recovery-20260915', 'source-recovery-resume-20260915')) {
        foreach ($x in @('wal', 'shm')) {
            $f = "E:\Codex\Frankie-BOSS-20260915\$d\source.sqlite-$x"
            if ((Test-Path $f) -and ((Get-Item $f).Length -le 32768)) { Remove-Item $f }
        }
    }
}
Get-ChildItem E:\bench -File | Select-Object Name, Length | Format-Table -AutoSize | Out-String
