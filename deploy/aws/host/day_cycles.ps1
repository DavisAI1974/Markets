$ErrorActionPreference = 'Stop'
# Stage 5 (cycles) of the unattended day pipeline: the day's result-bearing cycles, by wrapping
# operations/run_actual_sunday_ec2.py --configuration --compact-source-tools. That runner fixes
# the native numeric policy before model construction, then composes the
# compact-source host over the integrated classroom host and refuses when the classroom
# runner/adapter is absent from the lawful checkout (audit finding 3), so the base adapter can
# never be the one that runs.
#
# day_pipeline.py reaches this stage only under Greg's explicit --go naming the day's source
# manifest hash; without it the chain writes a HOLD receipt and this script is never sent.
#
# $Day, $ToolsRoot, $Python and $RunRoot are prepended by ssm_run_ps1.py --set from the pipeline
# configuration, so this file carries no path literal and no credential. host_runtime must declare
# pod_credential_ssm (name, region, trigger_directory): the Python process reads the private SSM
# value once and waits for each request's public readiness trigger. The LAST line is the stage receipt.
foreach ($required in 'Day', 'ToolsRoot', 'Python', 'RunRoot') {
    $value = Get-Variable -Name $required -ValueOnly -ErrorAction SilentlyContinue
    if (-not $value -or $value -like 'HOST_*') {
        throw "$required was not supplied by ssm_run_ps1.py --set (value: '$value')"
    }
}
$dayDirectory = Join-Path $RunRoot $Day
$requiresPrepared = (Get-Variable RequirePreparedConfiguration -ErrorAction SilentlyContinue) -and $RequirePreparedConfiguration
if ($requiresPrepared -and -not (Get-Variable PreparedConfigurationPath -ErrorAction SilentlyContinue)) {
    throw 'PreparedConfigurationPath required for the trading day'
}
if (Get-Variable PreparedConfigurationPath -ErrorAction SilentlyContinue) {
    if (-not $PreparedConfigurationSha256) { throw 'PreparedConfigurationSha256 required with PreparedConfigurationPath' }
    $configurationPath = $PreparedConfigurationPath
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $configurationPath).Hash.ToLower() -ne $PreparedConfigurationSha256) {
        throw 'Prepared configuration bytes changed'
    }
} else {
    $configurationPath = Join-Path $dayDirectory 'actual-host-configuration.json'
}
if (-not (Test-Path $configurationPath)) { throw "no run configuration for $Day at $configurationPath" }
$configuration = Get-Content $configurationPath -Raw | ConvertFrom-Json
if (-not $configuration.host_runtime.pod_credential_ssm) { throw 'cycles over SSM require pod_credential_ssm' }
$prefixesDirectory = $configuration.host_runtime.prefixes_directory
if (-not $prefixesDirectory) { throw "run configuration for $Day declares no host_runtime.prefixes_directory" }
$manifestPath = $configuration.host_runtime.prefix_manifest.path
if (-not (Test-Path $manifestPath)) { throw "cycles need the prefix manifest first; none at $manifestPath" }
$available = @((Get-Content $manifestPath -Raw | ConvertFrom-Json).witnesses).Count
$schedulePath = $configuration.host_runtime.schedule.path
if (-not $schedulePath -or -not (Test-Path -LiteralPath $schedulePath)) { throw 'Verified schedule required' }
$actualScheduleHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $schedulePath).Hash.ToLower()
if ($actualScheduleHash -ne $configuration.host_runtime.schedule.sha256) { throw 'Schedule bytes changed' }
$schedule = Get-Content -LiteralPath $schedulePath -Raw | ConvertFrom-Json
if ($requiresPrepared -or $configuration.trading_day -or $schedule.schema -eq 'BOSS_TRADING_DAY_CAUSAL_CYCLE_SCHEDULE_V1') {
    if (-not $PreparedConfigurationPath -or -not $PreparedConfigurationSha256 -or -not $ExpectedTradingDayScheduleSha256) {
        throw 'Trading day requires the receipted prepared configuration and schedule'
    }
    if ($configuration.trading_day -ne $Day -or $schedule.trading_day -ne $Day -or
        $schedule.schema -ne 'BOSS_TRADING_DAY_CAUSAL_CYCLE_SCHEDULE_V1' -or
        $schedule.schedule_sha256 -ne $ExpectedTradingDayScheduleSha256 -or
        $configuration.trading_day_schedule.schedule_sha256 -ne $ExpectedTradingDayScheduleSha256) {
        throw 'Prepared configuration or schedule differs from the requested trading day'
    }
}
$expected = @($schedule.steps).Count
if ($expected -lt 1) { throw 'Schedule declares no cycles' }
if (-not (Get-Variable CycleLimit -ErrorAction SilentlyContinue)) { $CycleLimit = $expected }
if ([int]$CycleLimit -lt 1 -or [int]$CycleLimit -gt $expected) { throw 'CycleLimit exceeds the declared schedule' }

if ($available -lt [int]$CycleLimit) { throw 'Requested cycles lack verified prefixes' }

$git = Get-Command git -ErrorAction SilentlyContinue
if ($git) { Write-Output ("TOOLS_HEAD=" + (& $git.Source -C $ToolsRoot rev-parse HEAD)) }
$tool = Join-Path $ToolsRoot 'research\kalshi\frankie_boss\operations\run_actual_sunday_ec2.py'
$resume = ''
if (Test-Path (Join-Path $configuration.run_directory 'native-host-runtime.json')) { $resume = '--ec2-resume' }
$pending = ''
$pendingReturnEnabled = (Get-Variable PendingReturn -ErrorAction SilentlyContinue) -and ([string]$PendingReturn -eq '1')
if ((Get-Variable PendingReturn -ErrorAction SilentlyContinue) -and ([string]$PendingReturn -notin @('0', '1'))) {
    throw 'PendingReturn must be 0 or 1'
}
if ($pendingReturnEnabled) {
    if (-not $PreparedConfigurationPath -or -not $PreparedConfigurationSha256 -or -not $ExpectedTradingDayScheduleSha256) {
        throw 'Pending return requires the pinned prepared configuration and schedule'
    }
    $pending = '--pending-return'
}
if (Get-Variable ResumeWaitSha256 -ErrorAction SilentlyContinue) {
    if (-not $pendingReturnEnabled -or ([string]$ResumeWaitSha256 -cnotmatch '^[0-9a-f]{64}$')) {
        throw 'ResumeWaitSha256 requires pending return and an exact receipt hash'
    }
    if (-not $resume) { throw 'A workflow event cannot start a new native run' }
    $pending += ' --resume-wait-sha256 ' + $ResumeWaitSha256
}
$log = Join-Path $dayDirectory ('day-cycles-' + [guid]::NewGuid().ToString('N') + '.log')
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = $ToolsRoot
Push-Location $ToolsRoot
try {
    # cmd.exe owns the redirection, as in the retained host scripts: under
    # $ErrorActionPreference='Stop' PowerShell turns a native command's first stderr line into a
    # terminating error, which is how two earlier runs lost their tracebacks.
    & cmd.exe /c "`"$Python`" `"$tool`" --configuration `"$configurationPath`" --compact-source-tools `"$ToolsRoot`" --cycles $CycleLimit $resume $pending > `"$log`" 2>&1"
    $code = $LASTEXITCODE
} finally { Pop-Location }
if (Test-Path $log) {
    Get-Content -LiteralPath $log
}

# The runner states its own outcome on its last JSON line. This script never infers a completion
# count from the filesystem: an incomplete run throws with the runner's own status, and the run
# resumes on the next dispatch from the same run directory.
$statusLine = $null
if (Test-Path $log) {
    $statusLine = Get-Content $log | Where-Object { $_.TrimStart().StartsWith('{') } | Select-Object -Last 1
}
# A lawful pending return is not completion. Python validates the original configuration
# and receipt bytes, retaining exact integer values; PowerShell never rewrites those documents.
if ($pendingReturnEnabled -and $code -in @(3, 4) -and $statusLine) {
    $waitModule = Join-Path $ToolsRoot 'research/kalshi/frankie_boss/operations/workflow_wait.py'
    $verifyPending = @'
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
try:
    module_path, configuration_path, log_path, exit_code, day, config_sha, schedule_sha, cycle_limit = sys.argv[1:]
    raw = Path(configuration_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != config_sha:
        raise ValueError('prepared configuration changed')
    configuration = json.loads(raw)
    spec = importlib.util.spec_from_file_location('retained_workflow_wait_validator', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    lines = Path(log_path).read_text(encoding='utf-8-sig').splitlines()
    status = json.loads(next(line for line in reversed(lines) if line.lstrip().startswith('{')))
    receipt = module.read_wait_receipt(status['receipt_path'], status['receipt_sha256'], configuration)
    if status != module.outcome(status['receipt_path'], receipt):
        raise ValueError('runner outcome differs from the retained receipt')
    if int(exit_code) != (3 if receipt['state'] == 'WAIT' else 4):
        raise ValueError('runner exit differs from retained pending state')
    schedule_pin = configuration['host_runtime']['schedule']
    schedule_raw = Path(schedule_pin['path']).read_bytes()
    schedule = json.loads(schedule_raw)
    if (hashlib.sha256(schedule_raw).hexdigest() != schedule_pin['sha256']
            or configuration.get('trading_day') != day or schedule.get('trading_day') != day
            or schedule.get('schema') != 'BOSS_TRADING_DAY_CAUSAL_CYCLE_SCHEDULE_V1'
            or schedule.get('schedule_sha256') != schedule_sha
            or configuration['trading_day_schedule']['schedule_sha256'] != schedule_sha
            or not 0 <= receipt['cycle_index'] < int(cycle_limit) <= len(schedule['steps'])):
        raise ValueError('pending run differs from prepared day or schedule')
    if hashlib.sha256(Path(configuration_path).read_bytes()).hexdigest() != config_sha:
        raise ValueError('prepared configuration changed during verification')
    result = dict(status, day=day, requested_cycles=int(cycle_limit), cycles_total=len(schedule['steps']),
        run_directory=configuration['run_directory'], run_id=configuration['run_id'],
        prepared_configuration_sha256=config_sha, schedule_sha256=schedule_sha)
    print(json.dumps(result,sort_keys=True,separators=(',', ':'),ensure_ascii=True,allow_nan=False))
except Exception:
    raise SystemExit('retained workflow wait refused') from None
'@
    $verifiedPending = & $Python -B -c $verifyPending $waitModule $configurationPath $log ([string]$code) $Day $PreparedConfigurationSha256 $ExpectedTradingDayScheduleSha256 ([string]$CycleLimit)
    if ($LASTEXITCODE -ne 0 -or -not $verifiedPending) { throw 'Pending receipt verification failed' }
    Write-Output ('PIPELINE_RECEIPT ' + ($verifiedPending -join ''))
    return
}
if ($code -ne 0 -or -not $statusLine) { throw "cycles exited $code for $Day; last status: $statusLine" }
$status = $statusLine | ConvertFrom-Json
if ($status.status -ne 'all_scheduled_cycles_complete' -and $status.status -ne 'all_nineteen_cycles_complete' -and $status.status -ne 'requested_cycles_complete') {
    throw "cycles did not complete for $Day; runner reported '$($status.status)'"
}
$receipt = [ordered]@{
    status           = $status.status
    requested_cycles = [int]$CycleLimit
    cycles_completed = [int]$status.cycles
    cycles_total     = $expected
    day              = $Day
    run_directory    = $configuration.run_directory
    run_id           = $configuration.run_id
}
Write-Output ('PIPELINE_RECEIPT ' + ($receipt | ConvertTo-Json -Compress))
