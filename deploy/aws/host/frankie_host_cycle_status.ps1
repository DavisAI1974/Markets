# Read-only status of the running (or last) cycles stage on the native host (2026-09-20).
#
# The binding probe's seven sections exceed the SSM output cap (~24 KB) once a run is past
# preparation, so this prints only what a running cycle shows: the runner's status lines and log
# tail, and the cycle directory's files with mtimes (host-service written after the trigger read;
# critic-spool/<job>/dispatch.json once the Granite request is on the Pod; completion and
# principal records as they land). Reads only; writes nothing; never opens the credential.
#
# $Day, $RunRoot arrive from ssm_run_ps1.py --set; no path literal here.
$ErrorActionPreference = 'Continue'
foreach ($required in 'Day', 'RunRoot') {
    $value = Get-Variable -Name $required -ValueOnly -ErrorAction SilentlyContinue
    if (-not $value -or $value -like 'HOST_*') { throw "$required was not supplied by ssm_run_ps1.py --set (value: '$value')" }
}
if (-not (Get-Variable CycleIndex -ErrorAction SilentlyContinue)) { $CycleIndex = '00' }
$dayDirectory = Join-Path $RunRoot $Day
$cfgPath = Join-Path $dayDirectory 'actual-host-configuration.json'
if (-not (Test-Path $cfgPath)) { Write-Output ("NO_CONFIG at " + $cfgPath); return }
$cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
$log = Join-Path $dayDirectory 'day-cycles.log'
Write-Output "### runner status lines (last 12) and log tail (last 8)"
if (Test-Path $log) {
    Write-Output ("log bytes=" + (Get-Item $log).Length + "  modified=" + (Get-Item $log).LastWriteTimeUtc.ToString('s') + 'Z')
    Select-String -Path $log -Pattern '"status": ?"' | Select-Object -Last 12 | ForEach-Object { '  ' + $_.Line.Substring(0, [Math]::Min(240, $_.Line.Length)) }
    Write-Output '  --- tail ---'
    Get-Content $log -Tail 8 | ForEach-Object { '  ' + $_.ToString().Substring(0, [Math]::Min(240, $_.ToString().Length)) }
} else { Write-Output ("NO_LOG at " + $log) }
Write-Output "### runner process"
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*run_actual_sunday*' } |
    ForEach-Object { '  pid=' + $_.ProcessId + ' since=' + $_.CreationDate.ToUniversalTime().ToString('s') + 'Z' }
$cycle = Join-Path $cfg.run_directory ('execution\cycle-' + $CycleIndex)
Write-Output ("### cycle-" + $CycleIndex + " files (name  mtime  bytes)")
if (Test-Path $cycle) {
    Get-ChildItem $cycle -Recurse -File | Sort-Object LastWriteTimeUtc | ForEach-Object {
        '  ' + $_.FullName.Substring($cycle.Length).TrimStart('\') + '  ' + $_.LastWriteTimeUtc.ToString('s') + 'Z  ' + $_.Length
    }
} else { Write-Output ("  absent: " + $cycle) }
Write-Output "### run-directory progress"
$progress = Join-Path $cfg.run_directory 'host-progress\progress.json'
if (Test-Path $progress) { '  ' + (Get-Content $progress -Raw).Substring(0, [Math]::Min(600, (Get-Content $progress -Raw).Length)) }
Write-Output '### done (read-only)'
