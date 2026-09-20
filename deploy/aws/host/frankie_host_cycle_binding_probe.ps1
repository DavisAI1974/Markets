# Read-only probe for the cycles-stage refusal of pipeline run 35508198333 (day 20211003).
#
# Diag run 35508442554 ruled out line 836 (the observer's admission equals the host's, key for key)
# and showed the 09-19 admitted witness and its host-preparation.c15.json living under
# <Codex>/actual-feedback-run/execution/cycle-00, while the day pipeline's cycles stage binds
# run_actual_sunday.py to the run_directory declared in <RunRoot>/<Day>/actual-host-configuration.json.
# This probe names which of the four checks in run_actual_sunday.py 812-843 refuses, by reading the
# runner's own traceback and by reconstructing each comparison from the files on disk.
#
# READ-ONLY. It starts, stops, writes and re-dispatches nothing, mints no host instance id, and
# creates no artifact outside $env:TEMP (removed at the end). The SSM parameter is not touched.
#
# $Day, $RunRoot, $ToolsRoot and $Python are prepended by ssm_run_ps1.py --set, so this file carries
# no path literal and no credential, exactly as day_cycles.ps1 does.
$ErrorActionPreference = 'Continue'
foreach ($required in 'Day', 'RunRoot', 'ToolsRoot', 'Python') {
    $value = Get-Variable -Name $required -ValueOnly -ErrorAction SilentlyContinue
    if (-not $value -or $value -like 'HOST_*') { throw "$required was not supplied by ssm_run_ps1.py --set (value: '$value')" }
}
if (-not (Get-Variable CycleIndex -ErrorAction SilentlyContinue)) { $CycleIndex = '00' }
$dayDirectory = Join-Path $RunRoot $Day
$cfgPath = Join-Path $dayDirectory 'actual-host-configuration.json'
# The 09-19 run directory that carries the admitted witness, derived from RunRoot's parent so that
# no absolute path is written into this file.
$legacyRoot = Join-Path (Split-Path $RunRoot -Parent) 'actual-feedback-run'

Write-Output "### 0 the runner's OWN traceback (day-cycles.log; the pipeline scrubs this, the host does not)"
$log = Join-Path $dayDirectory 'day-cycles.log'
if (Test-Path $log) {
    Write-Output ("path=" + $log + "  bytes=" + (Get-Item $log).Length + "  modified=" + (Get-Item $log).LastWriteTimeUtc.ToString('s') + 'Z')
    Write-Output '--- every Traceback / raise / Error line, with 2 lines of trailing context ---'
    Select-String -Path $log -Pattern 'Traceback \(most recent|^\s*raise |ValueError|RuntimeError|KeyError|FileNotFoundError|Error:' -Context 0, 2 |
        Select-Object -Last 40 | ForEach-Object {
            $_.Line; $_.Context.PostContext | ForEach-Object { '    | ' + $_ } }
    Write-Output '--- last 80 lines verbatim ---'
    Get-Content $log -Tail 80 | ForEach-Object { '  ' + $_ }
} else { Write-Output ("NO_LOG at " + $log) }

Write-Output "### 1 which run_directory the cycles stage binds to"
if (-not (Test-Path $cfgPath)) { Write-Output ("NO_CONFIG at " + $cfgPath); return }
$cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
$runDirectory = $cfg.run_directory
Write-Output ("configuration path = " + $cfgPath)
Write-Output ("run_id             = " + $cfg.run_id)
Write-Output ("run_directory      = " + $runDirectory)
Write-Output ("day directory      = " + $dayDirectory)
Write-Output ("run_directory equals day directory = " + ($runDirectory -and ((Resolve-Path $runDirectory -ErrorAction SilentlyContinue).Path -eq (Resolve-Path $dayDirectory -ErrorAction SilentlyContinue).Path)))
Write-Output ("09-19 witness root = " + $legacyRoot + "  exists=" + (Test-Path $legacyRoot))
Write-Output ("host_runtime.boss_commit = " + $cfg.host_runtime.boss_commit)
Write-Output ("host_runtime.repository  = " + $cfg.host_runtime.repository)

Write-Output "### 2 host-instance.c15.json in THAT run_directory, and in the two other candidate directories"
foreach ($pair in @(@('run_directory', $runDirectory), @('day directory', $dayDirectory), @('09-19 feedback run', $legacyRoot))) {
    $label = $pair[0]; $dir = $pair[1]
    $p = if ($dir) { Join-Path $dir 'host-instance.c15.json' } else { $null }
    if ($p -and (Test-Path $p)) {
        $rec = Get-Content $p -Raw | ConvertFrom-Json
        Write-Output ("  " + $label + ": instance_id=" + $rec.instance_id + " run_id=" + $rec.run_id + " keys=" + (($rec.PSObject.Properties | ForEach-Object { $_.Name }) -join ',') + " mtime=" + (Get-Item $p).LastWriteTimeUtc.ToString('s') + 'Z')
    } else { Write-Output ("  " + $label + ": host-instance.c15.json ABSENT" + $(if ($dir) { " (under " + $dir + ")" })) }
}
Write-Output "  NOTE: retained_instance_id() MINTS a fresh uuid when the file is absent from run_directory."

Write-Output "### 3 cycle-$CycleIndex listings under each candidate run directory"
foreach ($pair in @(@('run_directory', $runDirectory), @('09-19 feedback run', $legacyRoot))) {
    $label = $pair[0]; $dir = $pair[1]
    $cyc = if ($dir) { Join-Path (Join-Path $dir 'execution') ('cycle-' + $CycleIndex) } else { $null }
    Write-Output ("  --- " + $label + " -> " + $cyc)
    if ($cyc -and (Test-Path $cyc)) {
        Get-ChildItem $cyc | ForEach-Object { "      " + $_.Name + "  bytes=" + $(if ($_.PSIsContainer) { 'DIR' } else { $_.Length }) }
    } else { Write-Output "      ABSENT" }
}

Write-Output "### 4 the four comparisons of run_actual_sunday.py 812-843, with repr and the real exception"
$out = Join-Path $env:TEMP 'frankie_binding_probe.out'
Remove-Item $out -ErrorAction SilentlyContinue
$probe = @"
import json, os, sys, traceback
from pathlib import Path
log = open(r'$out', 'a', encoding='ascii', errors='replace')
def say(*a):
    line = ' '.join(str(x) for x in a)
    print(line, flush=True); log.write(line + '\n'); log.flush()
def load(path):
    return json.loads(Path(path).read_bytes())
try:
    cfg = load(r'$cfgPath')
    run_directory = Path(cfg['run_directory'])
    cycle = run_directory / 'execution' / 'cycle-$CycleIndex'
    request_id = '%s-cycle-$CycleIndex' % cfg['run_id']
    say('REPR run_directory =', repr(str(run_directory)), 'exists', run_directory.exists())
    say('REPR cycle_directory =', repr(str(cycle)), 'exists', cycle.exists())
    say('REPR request_id =', repr(request_id))

    # self.instance_id: read only; retained_instance_id() would MINT one, so this probe never calls it.
    inst_path = run_directory / 'host-instance.c15.json'
    instance_id = load(inst_path)['instance_id'] if inst_path.exists() else None
    say('REPR self.instance_id =', repr(instance_id), '(None means the file is absent and the runner mints a fresh uuid)')

    # The delivered trigger -> readiness directory -> service pins and startup intent.
    src = cfg['host_runtime'].get('pod_credential_ssm') or {}
    trig = Path(src.get('trigger_directory', '')) / request_id / 'FRANKIE_ACTUAL_EXECUTE_V1.json'
    say('REPR trigger =', repr(str(trig)), 'exists', trig.exists())
    trigger = load(trig) if trig.exists() else None
    ready = Path(trigger['readiness_directory']) if trigger else None
    say('REPR readiness_directory =', repr(str(ready)) if ready else 'None', 'exists', bool(ready and ready.exists()))
    pins = load(ready / 'service-pins.json') if ready and (ready / 'service-pins.json').exists() else None
    startup = load(ready / 'startup-intent.json') if ready and (ready / 'startup-intent.json').exists() else None

    # Which branch of line 779-822 the runner takes.
    service_record = cycle / 'host-service.c15.json'
    preparation = cycle / 'host-preparation.c15.json'
    say('BRANCH host-service.c15.json exists =', service_record.exists())
    say('BRANCH host-preparation.c15.json exists =', preparation.exists())
    say('BRANCH cycles.sqlite exists =', (run_directory / 'cycles.sqlite').exists())
    prepared = load(preparation) if preparation.exists() else None

    say('--- CHECK 1 (line 821) retained readiness has no admitted preparation ---')
    say('  prepared is None =', prepared is None,
        '| REFUSES here only on the service_record-exists branch; service_record exists =', service_record.exists())

    say('--- CHECK 2 (line 331) retained readiness differs from actual admission ---')
    if instance_id is None:
        say('  NOT EVALUATED: run_directory carries no host-instance.c15.json, so the runner mints a NEW')
        say('  instance id and host-ready-<new>.c15.json cannot pre-exist; this check cannot fire.')
    else:
        ready_path = cycle / ('host-ready-' + instance_id + '.c15.json')
        say('  REPR ready_path =', repr(str(ready_path)), 'exists', ready_path.exists())
        if ready_path.exists() and prepared is not None:
            record = load(ready_path)
            fields = dict(status='ACTUAL_INPUT_ADMITTED_WAITING_FOR_RETAINED_SERVICE',
                host_instance_id=instance_id, request_id=request_id,
                request_sha256=prepared['admission']['request_sha256'],
                request_path=prepared['request_path'],
                checkpoint_hash=prepared['initial_checkpoint_hash'],
                admission=prepared['admission'], model_forward_performed=False)
            on_disk = {k: v for k, v in record.items() if k != 'admitted_at'}
            say('  equal =', on_disk == fields)
            for k in sorted(set(on_disk) | set(fields)):
                if on_disk.get(k) != fields.get(k):
                    say('    DIFFERS', k, 'on_disk=', repr(on_disk.get(k))[:300], 'expected=', repr(fields.get(k))[:300])
        else:
            say('  NOT EVALUATED (witness or preparation absent in this cycle directory)')

    say('--- CHECK 3 (line 836) startup admission differs from the actual prepared request ---')
    if pins is None or prepared is None:
        say('  NOT EVALUATED: pins present =', pins is not None, '| prepared present =', prepared is not None)
    else:
        say('  REPR pins.request_sha256     =', repr(pins.get('request_sha256')))
        say('  REPR prepared.admission.request_sha256 =', repr(prepared['admission'].get('request_sha256')))
        say('  sha equal =', pins.get('request_sha256') == prepared['admission'].get('request_sha256'))
        say('  REPR pins.admission     =', repr(pins.get('admission')))
        say('  REPR prepared.admission =', repr(prepared['admission']))
        say('  admission equal =', pins.get('admission') == prepared['admission'])

    say('--- CHECK 4 (line 837) actual open run must follow this admitted live host instance ---')
    open_run = bool(trigger) and (ready / 'run.json').exists()
    say('  REPR open_run =', repr(open_run), '(run.json present in the readiness directory)')
    delivered = startup['local_ready']['host_instance_id'] if startup and 'local_ready' in startup else None
    say('  REPR startup.local_ready.host_instance_id =', repr(delivered))
    say('  REPR self.instance_id                     =', repr(instance_id))
    say('  equal =', delivered == instance_id)
    say('  REFUSES =', (not open_run) or delivered != instance_id)

    say('--- CHECK 5 (line 843) trusted host service pins differ ---')
    say('  NOT EVALUATED read-only: config_hash/identity_hash come from verified_service_inputs, which')
    say('  builds the RunpodConfig and the tokenizer admission. Pins side, for the record:')
    if pins is not None:
        for k in ('config_hash', 'identity_hash', 'runtime_sha256'):
            say('    REPR pins.' + k, '=', repr(pins.get(k)))
except BaseException as e:
    say('probe failed:', type(e).__name__, e); say(traceback.format_exc())
log.close(); sys.stdout.flush(); os._exit(0)
"@
$tmp = Join-Path $env:TEMP 'frankie_binding_probe.py'
Set-Content -Path $tmp -Value $probe -Encoding ASCII
$env:PYTHONDONTWRITEBYTECODE = '1'
& $Python $tmp 2>&1 | ForEach-Object { "$_" }
if (Test-Path $out) { Write-Output '--- probe file capture ---'; Get-Content $out }
Remove-Item $tmp, $out -ErrorAction SilentlyContinue
Write-Output '### done (nothing was written, started, stopped or dispatched)'
