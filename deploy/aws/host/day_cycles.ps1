$ErrorActionPreference = 'Stop'
# Stage 5 (cycles) of the unattended day pipeline: the day's result-bearing cycles, by wrapping
# operations/run_actual_sunday_compact_source.py --configuration. That runner composes the
# compact-source host over the integrated classroom host and refuses when the classroom
# runner/adapter is absent from the lawful checkout (audit finding 3), so the base adapter can
# never be the one that runs.
#
# day_pipeline.py reaches this stage only under Greg's explicit --go naming the day's source
# manifest hash; without it the chain writes a HOLD receipt and this script is never sent.
#
# $Day, $ToolsRoot, $Python and $RunRoot are prepended by ssm_run_ps1.py --set from the pipeline
# configuration, so this file carries no path literal and no credential. OPEN PREREQUISITE (spec
# prerequisite 6, still not built): the Pod credential reaches the runner on stdin, and SSM gives
# a sent script no stdin. Until that is wired as an SSM parameter read once, a cycle needing the
# Granite critic cannot complete from here. The LAST line is the stage's receipt.
foreach ($required in 'Day', 'ToolsRoot', 'Python', 'RunRoot') {
    $value = Get-Variable -Name $required -ValueOnly -ErrorAction SilentlyContinue
    if (-not $value -or $value -like 'HOST_*') {
        throw "$required was not supplied by ssm_run_ps1.py --set (value: '$value')"
    }
}
$dayDirectory = Join-Path $RunRoot $Day
$configurationPath = Join-Path $dayDirectory 'actual-host-configuration.json'
if (-not (Test-Path $configurationPath)) { throw "no run configuration for $Day at $configurationPath" }
$configuration = Get-Content $configurationPath -Raw | ConvertFrom-Json
$prefixesDirectory = $configuration.host_runtime.prefixes_directory
if (-not $prefixesDirectory) { throw "run configuration for $Day declares no host_runtime.prefixes_directory" }
$manifestPath = Join-Path $prefixesDirectory 'full19-prefix-witnesses.json'
if (-not (Test-Path $manifestPath)) { throw "cycles need the prefix manifest first; none at $manifestPath" }
$expected = @((Get-Content $manifestPath -Raw | ConvertFrom-Json).witnesses).Count

$git = Get-Command git -ErrorAction SilentlyContinue
if ($git) { Write-Output ("TOOLS_HEAD=" + (& $git.Source -C $ToolsRoot rev-parse HEAD)) }
$tool = Join-Path $ToolsRoot 'research\kalshi\frankie_boss\operations\run_actual_sunday_compact_source.py'
$log = Join-Path $dayDirectory 'day-cycles.log'
$env:PYTHONDONTWRITEBYTECODE = '1'
Push-Location $ToolsRoot
try {
    # cmd.exe owns the redirection, as in the retained host scripts: under
    # $ErrorActionPreference='Stop' PowerShell turns a native command's first stderr line into a
    # terminating error, which is how two earlier runs lost their tracebacks.
    & cmd.exe /c "`"$Python`" `"$tool`" --configuration `"$configurationPath`" --tools-root `"$ToolsRoot`" > `"$log`" 2>&1"
    $code = $LASTEXITCODE
} finally { Pop-Location }
if (Test-Path $log) {
    Get-Content $log -Tail 60 | ForEach-Object { $_.ToString().Substring(0, [Math]::Min(400, $_.ToString().Length)) }
}

# The runner states its own outcome on its last JSON line. This script never infers a completion
# count from the filesystem: an incomplete run throws with the runner's own status, and the run
# resumes on the next dispatch from the same run directory.
$statusLine = $null
if (Test-Path $log) {
    $statusLine = Get-Content $log | Where-Object { $_.TrimStart().StartsWith('{') } | Select-Object -Last 1
}
if ($code -ne 0 -or -not $statusLine) { throw "cycles exited $code for $Day; last status: $statusLine" }
$status = $statusLine | ConvertFrom-Json
if ($status.status -ne 'all_nineteen_cycles_complete') {
    throw "cycles did not complete for $Day; runner reported '$($status.status)'"
}
$receipt = [ordered]@{
    cycles_completed = [int]$status.cycles
    cycles_total     = $expected
    day              = $Day
    run_directory    = $configuration.run_directory
    run_id           = $configuration.run_id
}
Write-Output ('PIPELINE_RECEIPT ' + ($receipt | ConvertTo-Json -Compress))
