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
    ForEach-Object { '  pid=' + $_.ProcessId + ' since=' + $_.CreationDate.ToUniversalTime().ToString('s') + 'Z  threads=' + $_.ThreadCount + '  cpu_s=' + [Math]::Round(($_.KernelModeTime + $_.UserModeTime) / 1e7, 1) + '  ws_mb=' + [Math]::Round($_.WorkingSetSize / 1MB) }
# Greg, 2026-09-21: "check cpu usage to make sure there isn't only 1 running". Whole-host load, logical CPUs and
# every python process with its cumulative CPU seconds, so idle (HOLD) and busy (native step, 8 threads) read apart.
Write-Output "### host cpu (read-only)"
try {
    $cpuCount = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
    $load = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
    Write-Output ('  logical_cpus=' + $cpuCount + '  load_percent=' + [Math]::Round($load, 1))
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
        Sort-Object CreationDate | ForEach-Object {
            $cmd = if ($_.CommandLine) { $_.CommandLine } else { '' }
            $tail = if ($cmd.Length -gt 90) { $cmd.Substring($cmd.Length - 90) } else { $cmd }
            '  python pid=' + $_.ProcessId + ' threads=' + $_.ThreadCount + ' cpu_s=' + [Math]::Round(($_.KernelModeTime + $_.UserModeTime) / 1e7, 1) + ' ws_mb=' + [Math]::Round($_.WorkingSetSize / 1MB) + '  ...' + $tail
        }
} catch { Write-Output ('  cpu read failed: ' + $_.Exception.GetType().Name) }
$cycle = Join-Path $cfg.run_directory ('execution\cycle-' + $CycleIndex)
Write-Output ("### cycle-" + $CycleIndex + " files (name  mtime  bytes)")
if (Test-Path $cycle) {
    Get-ChildItem $cycle -Recurse -File | Sort-Object LastWriteTimeUtc | ForEach-Object {
        '  ' + $_.FullName.Substring($cycle.Length).TrimStart('\') + '  ' + $_.LastWriteTimeUtc.ToString('s') + 'Z  ' + $_.Length
    }
} else { Write-Output ("  absent: " + $cycle) }
Write-Output "### run-directory progress"
$progress = Join-Path $cfg.run_directory 'host-progress\progress.json'
if (Test-Path $progress) { $text = Get-Content $progress -Raw; '  ' + $text.Substring(0, [Math]::Min(600, $text.Length)) }
Write-Output "### root probe (Greg, 2026-09-20: follow Root as he works and pushes)"
# Root's session pushes four files to root/cycle-NN-response on origin and the host records the response as
# principal/session-response.json. ls-remote reads origin; a fetch of that one ref updates FETCH_HEAD only
# (the working tree stays clean for frankie_host_advance.ps1). Nothing else is written.
$response = Join-Path (Join-Path $cycle 'principal') 'session-response.json'
if (Test-Path $response) { $r = Get-Item $response; Write-Output ('  session-response.json  ' + $r.LastWriteTimeUtc.ToString('s') + 'Z  ' + $r.Length) }
else { Write-Output '  session-response.json absent (no response recorded on the host yet)' }
$tools = $cfg.host_runtime.repository
$gitExe = Get-Command git -ErrorAction SilentlyContinue
if ($gitExe -and $tools -and (Test-Path $tools)) {
    $rootRef = 'root/cycle-' + $CycleIndex + '-response'
    $heads = @(& $gitExe.Source -C $tools ls-remote --heads origin 'root/*' 2>&1)
    if ($heads.Count -gt 0) { $heads | ForEach-Object { Write-Output ('  origin: ' + $_) } } else { Write-Output '  no root/* branch on origin yet' }
    $head = @(& $gitExe.Source -C $tools ls-remote --heads origin $rootRef 2>$null)
    if ($head.Count -gt 0) {
        & $gitExe.Source -C $tools fetch -q origin $rootRef 2>&1 | Out-Null
        Write-Output ('  ' + $rootRef + ' head: ' + (& $gitExe.Source -C $tools log -1 --format='%H %cI %s' FETCH_HEAD))
        & $gitExe.Source -C $tools ls-tree -r -l FETCH_HEAD ('research/kalshi/frankie_boss/runs/' + $Day + '/root/') 2>$null | ForEach-Object { Write-Output ('    ' + $_) }
    } else { Write-Output ('  ' + $rootRef + ' not pushed yet') }
} else { Write-Output '  git or the tools checkout is unavailable for the root probe' }
Write-Output '### done (read-only)'
