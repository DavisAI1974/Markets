param(
    [string]$TaskName = "MarketsWatchPresentSignalStrengthMorning",
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$At = "02:00"
)

$ErrorActionPreference = "Stop"

$runner = Join-Path $RepoRoot "scripts\run_present_signal_strength_update.ps1"
if (-not (Test-Path $runner)) {
    throw "Missing runner script: $runner"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runner`" -RepoRoot `"$RepoRoot`""

$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 60)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Runs the markets-watch present-tense signal strength reanalysis each morning." `
    -Force | Out-Null

Write-Host "Installed scheduled task '$TaskName' to run daily at $At."
