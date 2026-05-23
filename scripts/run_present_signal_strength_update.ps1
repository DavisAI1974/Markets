param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$DataDir = ".",
    [string]$OutputDir = "pass22_present_signal_strength_out",
    [string]$NewsCouplingOutputDir = "pass23_news_coupling_out",
    [string]$Python = "python",
    [switch]$SkipNewsIngest,
    [switch]$NoMultiSignalPelt
)

$ErrorActionPreference = "Stop"

Set-Location $RepoRoot

$resolvedOutput = Join-Path $RepoRoot $OutputDir
New-Item -ItemType Directory -Force -Path $resolvedOutput | Out-Null

$logPath = Join-Path $resolvedOutput "present_strength_morning_update.log"
$started = Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"
"[$started] starting present signal strength update" | Tee-Object -FilePath $logPath -Append

if (-not $SkipNewsIngest) {
    "[$(Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz")] ingesting daily news" | Tee-Object -FilePath $logPath -Append
    & $Python "news_ingest_rss.py" `
        "--output" "news_events.jsonl" `
        "--raw-output" "news_raw_ingest.jsonl" `
        "--lookback-hours" "36" 2>&1 | Tee-Object -FilePath $logPath -Append
    if ($LASTEXITCODE -ne 0) {
        "[$(Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz")] news ingest failed with exit code $LASTEXITCODE" | Tee-Object -FilePath $logPath -Append
        exit $LASTEXITCODE
    }

    "[$(Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz")] running news coupling research" | Tee-Object -FilePath $logPath -Append
    & $Python "news_coupling_research.py" `
        "--data-dir" $DataDir `
        "--events" "news_events.jsonl" `
        "--output-dir" $NewsCouplingOutputDir 2>&1 | Tee-Object -FilePath $logPath -Append
    if ($LASTEXITCODE -ne 0) {
        "[$(Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz")] news coupling failed with exit code $LASTEXITCODE" | Tee-Object -FilePath $logPath -Append
        exit $LASTEXITCODE
    }

    "[$(Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz")] deriving news policy" | Tee-Object -FilePath $logPath -Append
    & $Python "build_news_policy_from_coupling.py" `
        "--coupling-results" (Join-Path $NewsCouplingOutputDir "news_coupling_results.json") `
        "--output" "news_policy.json" 2>&1 | Tee-Object -FilePath $logPath -Append
    if ($LASTEXITCODE -ne 0) {
        "[$(Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz")] news policy failed with exit code $LASTEXITCODE" | Tee-Object -FilePath $logPath -Append
        exit $LASTEXITCODE
    }

    "[$(Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz")] building daily news context" | Tee-Object -FilePath $logPath -Append
    & $Python "build_daily_news_context.py" `
        "--events" "news_events.jsonl" `
        "--policy" "news_policy.json" `
        "--output" "daily_news_context.json" `
        "--max-age-hours" "36" 2>&1 | Tee-Object -FilePath $logPath -Append
    if ($LASTEXITCODE -ne 0) {
        "[$(Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz")] daily news context failed with exit code $LASTEXITCODE" | Tee-Object -FilePath $logPath -Append
        exit $LASTEXITCODE
    }
}

$argsList = @(
    "present_signal_strength_reanalysis.py",
    "--data-dir", $DataDir,
    "--output-dir", $OutputDir
)

if (-not $NoMultiSignalPelt) {
    $argsList += "--multi-signal-pelt"
}

& $Python @argsList 2>&1 | Tee-Object -FilePath $logPath -Append
$exitCode = $LASTEXITCODE

$finished = Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"
if ($exitCode -ne 0) {
    "[$finished] failed with exit code $exitCode" | Tee-Object -FilePath $logPath -Append
    exit $exitCode
}

"[$finished] completed present signal strength update" | Tee-Object -FilePath $logPath -Append
