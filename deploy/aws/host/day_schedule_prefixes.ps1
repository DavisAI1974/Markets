$ErrorActionPreference = 'Stop'
# Stage 4 (schedule-prefixes) of the unattended day pipeline: build the day's remaining Sunday
# prefixes by wrapping operations/build_remaining_sunday_prefixes.py --configuration.
#
# $Day, $ToolsRoot, $Python and $RunRoot are prepended by ssm_run_ps1.py --set from the pipeline
# configuration, so this file carries no path literal and no credential. Nothing here rebuilds the
# prefix or reducer machinery: the gold standard is the builder, and this only runs it and reads
# back what it wrote. The LAST line is the stage's receipt, which day_pipeline.py parses.
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

$git = Get-Command git -ErrorAction SilentlyContinue
if ($git) { Write-Output ("TOOLS_HEAD=" + (& $git.Source -C $ToolsRoot rev-parse HEAD)) }
$tool = Join-Path $ToolsRoot 'research\kalshi\frankie_boss\operations\build_remaining_sunday_prefixes.py'
$log = Join-Path $dayDirectory 'day-schedule-prefixes.log'
$env:PYTHONDONTWRITEBYTECODE = '1'
Push-Location $ToolsRoot
try {
    # cmd.exe owns the redirection: under $ErrorActionPreference='Stop' PowerShell turns a native
    # command's first stderr line into a terminating error, which is how two earlier runs lost
    # their tracebacks.
    & cmd.exe /c "`"$Python`" `"$tool`" --configuration `"$configurationPath`" > `"$log`" 2>&1"
    $code = $LASTEXITCODE
} finally { Pop-Location }
if (Test-Path $log) {
    Get-Content $log -Tail 40 | ForEach-Object { $_.ToString().Substring(0, [Math]::Min(400, $_.ToString().Length)) }
}
if ($code -ne 0) { throw "build_remaining_sunday_prefixes exited $code for $Day" }

# The receipt is read back from what the builder wrote, never from this script's expectations.
$manifestPath = Join-Path $prefixesDirectory 'full19-prefix-witnesses.json'
if (-not (Test-Path $manifestPath)) { throw "the builder left no full19-prefix-witnesses.json in $prefixesDirectory" }
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
$witnessed = @($manifest.witnesses).Count
if ($witnessed -ne [int]$manifest.prefixes) {
    throw "prefix manifest disagrees with itself: $witnessed witnesses against prefixes=$($manifest.prefixes)"
}
$receipt = [ordered]@{
    prefix_count    = $witnessed
    prefixes_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $manifestPath).Hash.ToLower()
    day             = $Day
    manifest        = $manifestPath
}
Write-Output ('PIPELINE_RECEIPT ' + ($receipt | ConvertTo-Json -Compress))
