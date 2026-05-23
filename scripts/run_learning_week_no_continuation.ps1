param(
    [int]$StrideMinutes = 60,
    [int]$SliceHours = 24,
    [int]$TotalHours = 168
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root "mock_replay_learning_week1_no_continuation_logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Allowed = "MEAN_REVERSION_CHOP,NEWS_BREAKOUT,LIQUIDITY_SQUEEZE"
$Summary = @()

for ($StartHour = 0; $StartHour -lt $TotalHours; $StartHour += $SliceHours) {
    $Hours = [Math]::Min($SliceHours, $TotalHours - $StartHour)
    $OutDir = Join-Path $Root ("mock_replay_learning_week1_no_continuation_h{0}_stride{1}_out" -f $StartHour, $StrideMinutes)
    $LogPath = Join-Path $LogDir ("slice_h{0}_stride{1}.log" -f $StartHour, $StrideMinutes)
    $AutoPath = Join-Path $OutDir "market_strategy_autoresearch_all_results.json"

    Push-Location $Root
    try {
        "[$(Get-Date -Format o)] START slice start_hour=$StartHour hours=$Hours stride=$StrideMinutes" | Tee-Object -FilePath $LogPath -Append
        python mock_trade_replay.py `
            --data-dir . `
            --output-dir $OutDir `
            --start-hour $StartHour `
            --hours $Hours `
            --stride-minutes $StrideMinutes `
            --checkpoint-hours 0 `
            --disable-news-context `
            --no-enforce-bucket-health `
            --no-enforce-daily-limits `
            --allowed-strategies $Allowed 2>&1 | Tee-Object -FilePath $LogPath -Append

        if (Test-Path (Join-Path $OutDir "mock_replay_results.json")) {
            python market_strategy_autoresearch.py `
                --replay-results (Join-Path $OutDir "mock_replay_results.json") `
                --output-path $AutoPath `
                --strategies ALL 2>&1 | Tee-Object -FilePath $LogPath -Append
        }

        "[$(Get-Date -Format o)] END slice start_hour=$StartHour" | Tee-Object -FilePath $LogPath -Append
        $Summary += [PSCustomObject]@{
            start_hour = $StartHour
            hours = $Hours
            stride_minutes = $StrideMinutes
            output_dir = $OutDir
            log_path = $LogPath
            status = "done"
        }
    } catch {
        "[$(Get-Date -Format o)] ERROR slice start_hour=$StartHour $_" | Tee-Object -FilePath $LogPath -Append
        $Summary += [PSCustomObject]@{
            start_hour = $StartHour
            hours = $Hours
            stride_minutes = $StrideMinutes
            output_dir = $OutDir
            log_path = $LogPath
            status = "error"
            error = "$_"
        }
    } finally {
        Pop-Location
    }
}

$SummaryPath = Join-Path $LogDir ("summary_stride{0}.json" -f $StrideMinutes)
$Summary | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $SummaryPath
"[$(Get-Date -Format o)] wrote $SummaryPath" | Tee-Object -FilePath (Join-Path $LogDir "runner.log") -Append
