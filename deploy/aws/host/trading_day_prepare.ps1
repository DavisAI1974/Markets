$ErrorActionPreference = 'Stop'
# Data preparation only. Explicit paths select new output; original evidence is preserved.
foreach ($required in 'ToolsRoot', 'Python', 'LaunchConfigurationPath', 'PreparedConfigurationPath') {
    $value = Get-Variable -Name $required -ValueOnly -ErrorAction SilentlyContinue
    if (-not $value) { throw "$required is required" }
}
if (Test-Path -LiteralPath $PreparedConfigurationPath) { throw 'Prepared configuration already exists; preserve it' }
$tool = Join-Path $ToolsRoot 'research\kalshi\frankie_boss\operations\prepare_trading_day.py'
$arguments = @($tool, '--configuration', $LaunchConfigurationPath, '--output-configuration', $PreparedConfigurationPath)
if (Get-Variable CycleLimit -ErrorAction SilentlyContinue) { $arguments += @('--cycles', [string]$CycleLimit) }
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = $ToolsRoot
# Direct argument-array invocation preserves paths without constructing shell command text.
& $Python @arguments
if ($LASTEXITCODE -ne 0) { throw "Trading-day preparation exited $LASTEXITCODE" }
