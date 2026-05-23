$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$env:MARKETS_WATCH_LIVE = "1"
$env:MARKETS_WATCH_LIVE_DATA_DIR = Join-Path $PSScriptRoot "live_data"
$env:MARKETS_WATCH_POLL_INTERVAL_S = "5"
$env:MARKETS_WATCH_CHUNK_MIN_SEGMENT = "3"
$env:MARKETS_WATCH_DEMO_MODE = "0"
$env:MARKETS_WATCH_API = "http://localhost:8000"
$env:MARKETS_WATCH_APP_URL = "http://localhost:5174"

New-Item -ItemType Directory -Force -Path $env:MARKETS_WATCH_LIVE_DATA_DIR | Out-Null
$liveReplayOut = Join-Path $PSScriptRoot "research\strategy_evolution\live_mock_replay"
$compareOut = Join-Path $PSScriptRoot "research\strategy_evolution\live_family_registry_compare"
$exitParams = Join-Path $PSScriptRoot "research\strategy_evolution\exit_params_h0_h168_v2_promoted_min5.json"
New-Item -ItemType Directory -Force -Path $liveReplayOut | Out-Null
New-Item -ItemType Directory -Force -Path $compareOut | Out-Null

function Test-MarketsProcessRunning {
  param([string]$MatchPattern)
  if ([string]::IsNullOrWhiteSpace($MatchPattern)) {
    return $false
  }
  $escaped = [regex]::Escape($MatchPattern)
  $matches = Get-CimInstance Win32_Process |
    Where-Object {
      $_.ProcessId -ne $PID -and
      $_.CommandLine -and
      $_.CommandLine -match $escaped -and
      $_.CommandLine -notlike '*Get-CimInstance Win32_Process*' -and
      ($_.Name -eq 'python.exe' -or $_.Name -eq 'node.exe' -or $_.CommandLine -like '*-NoExit*')
    }
  return @($matches).Count -gt 0
}

function Start-MarketsProcess {
  param(
    [string]$Title,
    [string]$Command,
    [string]$MatchPattern = ""
  )
  if (Test-MarketsProcessRunning $MatchPattern) {
    Write-Host "already running $Title"
    return
  }
  Start-Process powershell -WindowStyle Hidden -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd `"$PSScriptRoot`"; $Command"
  ) | Out-Null
  Write-Host "started $Title"
}

Start-MarketsProcess "live collectors" "while (`$true) { python live_collectors.py --save-interval 2 --archive-dir `"live_data_history`" --archive-interval 60; Write-Host '[watchdog] live_collectors.py exited; restarting in 5s'; Start-Sleep -Seconds 5 }" "live_collectors.py"
Start-Sleep -Seconds 4
Start-MarketsProcess "live mock replay runner" "python live_mock_trade_replay.py --data-dir `"$env:MARKETS_WATCH_LIVE_DATA_DIR`" --output-dir `"$liveReplayOut`" --exit-params `"$exitParams`" --poll-seconds 5 --report-seconds 3600 --skip-existing-on-start" "live_mock_trade_replay.py"
Start-Sleep -Seconds 1
Start-MarketsProcess "live family registry compare sidecar" "while (`$true) { python live_family_registry_compare.py --data-dir `"$env:MARKETS_WATCH_LIVE_DATA_DIR`" --output-root `"$compareOut`" --exit-params `"$exitParams`" --duration-seconds 0 --poll-seconds 5; Write-Host '[watchdog] live_family_registry_compare.py exited; restarting in 10s'; Start-Sleep -Seconds 10 }" "live_family_registry_compare.py"
Start-Sleep -Seconds 1
Start-MarketsProcess "live hindsight evolve worker" "while (`$true) { python live_hindsight_evolve_worker.py --run-audit --interval-seconds 300 --max-candidates 12 --family-budget 7; Write-Host '[watchdog] live_hindsight_evolve_worker.py exited; restarting in 10s'; Start-Sleep -Seconds 10 }" "live_hindsight_evolve_worker.py"
Start-Sleep -Seconds 1
Start-MarketsProcess "bank allocation shadow reporter" "while (`$true) { python summarize_live_bank_allocation_shadow.py | Out-Null; Start-Sleep -Seconds 120 }" "summarize_live_bank_allocation_shadow.py"
Start-Sleep -Seconds 1
Start-MarketsProcess "sidecar exit restatement reporter" "while (`$true) { python build_live_sidecar_exit_restatement.py --target-notional-usd 10000 --compare-run-limit 40 --update-pairings | Out-Null; Start-Sleep -Seconds 300 }" "build_live_sidecar_exit_restatement.py"
Start-Sleep -Seconds 1
Start-MarketsProcess "15 minute live stack health reporter" "while (`$true) { python live_stack_health.py; Start-Sleep -Seconds 900 }" "live_stack_health.py"
Start-Sleep -Seconds 1
Start-MarketsProcess "hourly live analysis reporter" "while (`$true) { python live_hourly_analysis_report.py --print-md; Start-Sleep -Seconds 3600 }" "live_hourly_analysis_report.py"
Start-Sleep -Seconds 1
Start-MarketsProcess "api server" "`$env:MARKETS_WATCH_LIVE='1'; `$env:MARKETS_WATCH_LIVE_DATA_DIR='$env:MARKETS_WATCH_LIVE_DATA_DIR'; `$env:MARKETS_WATCH_POLL_INTERVAL_S='5'; `$env:MARKETS_WATCH_CHUNK_MIN_SEGMENT='3'; `$env:MARKETS_WATCH_DEMO_MODE='0'; python -m uvicorn backend.api_server:app --host 0.0.0.0 --port 8000" "uvicorn backend.api_server:app"
Start-Sleep -Seconds 2
Start-MarketsProcess "vite frontend" "cd frontend; npm run dev -- --host 0.0.0.0 --port 5174" "npm run dev"

Write-Host ""
Write-Host "Live proof-of-concept stack is starting."
Write-Host "App:     http://localhost:5174"
Write-Host "API:     http://localhost:8000/api/health"
Write-Host "Live bin files: $env:MARKETS_WATCH_LIVE_DATA_DIR"
Write-Host ""
Write-Host "Tape data appears first. Market reads need a few live minutes to warm up."
