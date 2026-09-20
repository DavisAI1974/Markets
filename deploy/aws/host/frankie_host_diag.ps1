# Read-only diagnostic for run 35498663360 (day 20211003). Reads files and reports; starts, stops,
# writes and re-dispatches nothing. The SSM parameter VALUE is never printed, only its type and size class.
$ErrorActionPreference = 'Continue'
$day = 'C:/Codex/Frankie-BOSS-20260919/days/20211003'
$log = Join-Path $day 'day-cycles.log'
$cfg = Join-Path $day 'actual-host-configuration.json'
$py  = 'C:/Codex/Frankie-BOSS-20260919/actual-host-python/Scripts/python.exe'

Write-Output "### 1 day-cycles.log"
if (Test-Path $log) {
  Write-Output ("bytes=" + (Get-Item $log).Length)
  $waiting = Select-String -Path $log -SimpleMatch 'waiting_for_request_bound_service_trigger' | Measure-Object | Select-Object -ExpandProperty Count
  Write-Output ("waiting_for_request_bound_service_trigger lines=" + $waiting)
  Write-Output "--- status lines (actual_input_admitted / stopped / trigger) ---"
  Select-String -Path $log -Pattern '"status": ?"(actual_input_admitted|stopped|waiting_for_request_bound_service_trigger|same_job_recovery)' | ForEach-Object { $_.Line.Substring(0, [Math]::Min(700, $_.Line.Length)) }
  Write-Output "--- last 12 FRANKIE_PROGRESS phases ---"
  Select-String -Path $log -SimpleMatch 'FRANKIE_PROGRESS' | Select-Object -Last 12 | ForEach-Object {
    $l = $_.Line; $p = [regex]::Match($l, '"phase":"([a-z_]+)"').Groups[1].Value; $k = [regex]::Match($l, '"kind":"([a-z_]+)"').Groups[1].Value
    $e = [regex]::Match($l, '"elapsed_seconds":([0-9.]+)').Groups[1].Value; $c = [regex]::Match($l, '"code":"([a-z_]+)"').Groups[1].Value
    Write-Output ("  kind=$k phase=$p elapsed=$e code=$c") }
} else { Write-Output "NO_LOG" }

Write-Output "### 1b which code actually ran: TOOLS_HEAD from the log, and the host checkout"
if (Test-Path $log) { Select-String -Path $log -SimpleMatch 'TOOLS_HEAD=' | ForEach-Object { $_.Line } }
$tools = 'C:/tools/Frankie-20260919/Markets'
$gitExe = Get-Command git -ErrorAction SilentlyContinue
if ($gitExe -and (Test-Path $tools)) {
  Write-Output ("host checkout HEAD: " + (& $gitExe.Source -C $tools log -1 --format='%H %ad %s' --date=short))
  Write-Output ("host checkout branch: " + (& $gitExe.Source -C $tools rev-parse --abbrev-ref HEAD))
  $ras = Join-Path $tools 'research/kalshi/frankie_boss/operations/run_actual_sunday.py'
  if (Test-Path $ras) {
    $n = (Select-String -Path $ras -SimpleMatch 'read_execution_trigger' | Measure-Object).Count
    $m = (Select-String -Path $ras -SimpleMatch 'pod_credential_ssm' | Measure-Object).Count
    Write-Output ("host run_actual_sunday.py: read_execution_trigger=" + $n + " pod_credential_ssm=" + $m)
  } else { Write-Output "host run_actual_sunday.py: MISSING" }
} else { Write-Output "host checkout or git not found" }

Write-Output "### 1c the LAWFUL checkout (host_runtime.repository / boss_commit): the code that actually imports ActualHost"
if (Test-Path $cfg) {
  $c0 = Get-Content $cfg -Raw | ConvertFrom-Json
  $repo = $c0.host_runtime.repository
  Write-Output ("host_runtime.repository=" + $repo)
  Write-Output ("host_runtime.boss_commit=" + $c0.host_runtime.boss_commit)
  Write-Output ("host_runtime.completion_workflow_ref=" + $c0.host_runtime.completion_workflow_ref)
  if ($repo -and (Test-Path $repo)) {
    if ($gitExe) {
      Write-Output ("lawful checkout HEAD: " + (& $gitExe.Source -C $repo log -1 --format='%H %ad %s' --date=short))
      Write-Output ("lawful checkout branch: " + (& $gitExe.Source -C $repo rev-parse --abbrev-ref HEAD))
    }
    $lras = Join-Path $repo 'research/kalshi/frankie_boss/operations/run_actual_sunday.py'
    if (Test-Path $lras) {
      $ln = (Select-String -Path $lras -SimpleMatch 'read_execution_trigger' | Measure-Object).Count
      $lm = (Select-String -Path $lras -SimpleMatch 'pod_credential_ssm' | Measure-Object).Count
      $ls = (Select-String -Path $lras -SimpleMatch 'waiting_for_request_bound_service_trigger' | Measure-Object).Count
      Write-Output ("lawful run_actual_sunday.py: read_execution_trigger=" + $ln + " pod_credential_ssm=" + $lm + " waiting_line=" + $ls)
    } else { Write-Output "lawful run_actual_sunday.py: MISSING" }
  } else { Write-Output "lawful repository path missing or absent" }
}

Write-Output "### 1d PROBE: call read_execution_trigger on a bare host object with the real config (10 s cap; prints the REAL exception message)"
$tools = 'C:/tools/Frankie-20260919/Markets'
if ((Test-Path $py) -and (Test-Path $tools) -and (Test-Path $cfg)) {
  $out3 = Join-Path $env:TEMP 'frankie_diag_probe.out'
  Remove-Item $out3 -ErrorAction SilentlyContinue
  $probe = @"
import json, sys, threading, os, traceback
log = open(r'$out3', 'a', encoding='ascii', errors='replace')
def say(*a):
    line = ' '.join(str(x) for x in a)
    print(line, flush=True); log.write(line + '\n'); log.flush()
try:
    sys.path.insert(0, r'$tools')
    from research.kalshi.frankie_boss.operations import run_actual_sunday as actual
    cfg = json.loads(open(r'$cfg', 'rb').read())
    h = actual.ActualHost.__new__(actual.ActualHost)
    h.config = cfg; h.host = cfg['host_runtime']
    say('probe module file:', actual.__file__)
    say('probe host has pod_credential_ssm:', 'pod_credential_ssm' in h.host)
    rid = cfg['run_id'] + '-cycle-00'
    import re as _re
    src = h.host.get('pod_credential_ssm')
    say('REPR source type:', type(src).__name__, 'keys:', repr(sorted(src)) if isinstance(src, dict) else 'n/a')
    if isinstance(src, dict):
        for k in ('name', 'region', 'trigger_directory'):
            say('REPR', k, '=', repr(src.get(k)), 'type', type(src.get(k)).__name__)
    say('REPR run_id =', repr(cfg.get('run_id')), 'type', type(cfg.get('run_id')).__name__)
    say('REPR request_id =', repr(rid))
    if isinstance(src, dict):
        say('COND keyset_ok:', set(src) == {'name', 'region', 'trigger_directory'})
        say('COND name_ok:', bool(_re.fullmatch(r'/[A-Za-z0-9_./-]{1,1000}', str(src.get('name')))))
        say('COND region_ok:', bool(_re.fullmatch(r'[a-z]{2}(?:-[a-z]+)+-\d', str(src.get('region')))))
        say('COND trigger_dir_ok:', bool(src.get('trigger_directory')))
    say('COND run_id_ok:', bool(_re.fullmatch(r'[A-Za-z0-9_-]{1,128}', str(cfg.get('run_id', '')))))
    say('COND request_in_set:', rid in {'%s-cycle-%02d' % (cfg['run_id'], i) for i in range(19)})
    say('COND self.config is cfg:', h.config is cfg, '| getattr config run_id =', repr(getattr(h, 'config', {}).get('run_id', '')))
    result = {}
    def call():
        try:
            h.read_execution_trigger('FRANKIE_ACTUAL_EXECUTE_V1', ('readiness_directory', 'service_pins_sha256'), rid)
            result['outcome'] = 'RETURNED'
        except BaseException as e:
            result['outcome'] = 'RAISED %s: %s' % (type(e).__name__, e)
            result['trace'] = traceback.format_exc()
    t = threading.Thread(target=call, daemon=True); t.start(); t.join(10)
    say('probe outcome:', result.get('outcome', 'STILL WAITING after 10 s (shape check passed; it is looping on the absent trigger)'))
    if 'trace' in result: say(result['trace'])
except BaseException as e:
    say('probe setup failed:', type(e).__name__, e); say(traceback.format_exc())
log.close(); sys.stdout.flush(); os._exit(0)
"@
  $tmp3 = Join-Path $env:TEMP 'frankie_diag_probe.py'; Set-Content -Path $tmp3 -Value $probe -Encoding ASCII
  Push-Location $tools; $env:PYTHONPATH = $tools; $env:PYTHONDONTWRITEBYTECODE = '1'
  try { & $py $tmp3 2>&1 | ForEach-Object { "$_" } } catch { Write-Output ("probe invocation error: " + $_) } finally { Pop-Location }
  if (Test-Path $out3) { Write-Output "--- probe file capture ---"; Get-Content $out3 } else { Write-Output "probe file capture: NONE" }
  Remove-Item $tmp3 -ErrorAction SilentlyContinue; Remove-Item $out3 -ErrorAction SilentlyContinue
} else { Write-Output "probe skipped (python, tools or config missing)" }

Write-Output "### 2 actual-host-configuration.json -> pod_credential_ssm, run_id"
$src = $null
if (Test-Path $cfg) {
  $c = Get-Content $cfg -Raw | ConvertFrom-Json
  $src = $c.host_runtime.pod_credential_ssm
  Write-Output ("run_id=" + $c.run_id)
  if ($src) { Write-Output ("pod_credential_ssm: name=" + $src.name + " region=" + $src.region + " trigger_directory=" + $src.trigger_directory)
    Write-Output ("pod_credential_ssm EXACT KEY SET: " + (($src.PSObject.Properties | ForEach-Object { $_.Name }) -join ',')) }
  else { Write-Output "pod_credential_ssm: ABSENT" }
  Write-Output ("host_runtime keys: " + (($c.host_runtime.PSObject.Properties | ForEach-Object { $_.Name }) -join ','))
  Write-Output ("top-level keys: " + (($c.PSObject.Properties | ForEach-Object { $_.Name }) -join ','))
  Write-Output ("native-host-runtime.json (resume marker) present=" + (Test-Path (Join-Path $c.run_directory 'native-host-runtime.json')))
} else { Write-Output "NO_CONFIG" }

Write-Output "### 3 trigger file for cycle 00"
if ($src -and $c.run_id) {
  $req = $c.run_id + '-cycle-00'
  $trig = Join-Path (Join-Path $src.trigger_directory $req) 'FRANKIE_ACTUAL_EXECUTE_V1.json'
  Write-Output ("path=" + $trig)
  if (Test-Path $trig) {
    $t = Get-Content $trig -Raw | ConvertFrom-Json
    Write-Output ("EXISTS  readiness_directory=" + $t.readiness_directory + "  service_pins_sha256=" + $t.service_pins_sha256)
    $rd = $t.readiness_directory
    if ($rd) { foreach ($f in 'service-pins.json','service-ready.json','pod-info.json','run.json','startup-intent.json') {
      Write-Output ("  readiness/" + $f + " present=" + (Test-Path (Join-Path $rd $f))) } }
  } else { Write-Output "ABSENT" }
  $tdir = Join-Path $src.trigger_directory $req
  if (Test-Path $tdir) { Write-Output "request dir listing:"; Get-ChildItem $tdir | ForEach-Object { "  " + $_.Name } }
} else { Write-Output "skipped (no source/run_id)" }

Write-Output "### 3b the local input-admitted witness (credential-free by design) and the cycle-00 directory"
$cyc = 'C:/Codex/Frankie-BOSS-20260919/actual-feedback-run/execution/cycle-00'
if (Test-Path $cyc) {
  Write-Output "cycle-00 listing:"; Get-ChildItem $cyc | ForEach-Object { "  " + $_.Name + "  " + $_.Length }
  $hr = Get-ChildItem $cyc -Filter 'host-ready-*.c15.json' | Select-Object -First 1
  if ($hr) { Write-Output ("host-ready file: " + $hr.Name + " bytes=" + $hr.Length); Write-Output "----- BEGIN local_ready_json -----"; Get-Content $hr.FullName -Raw; Write-Output "----- END local_ready_json -----" }
  else { Write-Output "host-ready file: NONE" }
} else { Write-Output "cycle-00 directory ABSENT" }

Write-Output "### 3c can the HOST role read the retained readiness bucket (us-east-1)?"
if (Test-Path $py) {
  $code2 = @"
try:
    import boto3, botocore
    s3 = boto3.client('s3', region_name='us-east-1')
    r = s3.list_objects_v2(Bucket='frankie-granite42-568968024170-us-east-1', Prefix='retained-granite/6cd46f983845fbd2ed88ec24ebf18f446cc3523a89307b03290351bd39d3b0dd/', MaxKeys=5)
    keys = [o['Key'] for o in r.get('Contents', [])]
    print('S3 LIST OK objects_under_new_request_prefix=%d' % len(keys))
    for k in keys: print('  ' + k)
except botocore.exceptions.ClientError as e:
    print('S3 LIST FAIL code=%s' % e.response['Error']['Code'])
except Exception as e:
    print('S3 LIST FAIL type=%s' % type(e).__name__)
"@
  $tmp2 = Join-Path $env:TEMP 'frankie_diag_s3.py'; Set-Content -Path $tmp2 -Value $code2 -Encoding ASCII
  & $py $tmp2
  Remove-Item $tmp2 -ErrorAction SilentlyContinue
} else { Write-Output "skipped (host python missing)" }

Write-Output "### 4 SSM parameter readable by the HOST role (value never printed)"
if ($src -and (Test-Path $py)) {
  $code = @"
import sys
try:
    import boto3, botocore
    p = boto3.client('ssm', region_name='$($src.region)').get_parameter(Name='$($src.name)', WithDecryption=True)['Parameter']
    v = p.get('Value') or ''
    print('GET_PARAMETER OK type=%s value_len_class=%s' % (p.get('Type'), '32-256' if 32 <= len(v) <= 256 else 'out-of-range'))
except botocore.exceptions.ClientError as e:
    print('GET_PARAMETER FAIL code=%s' % e.response['Error']['Code'])
except Exception as e:
    print('GET_PARAMETER FAIL type=%s' % type(e).__name__)
"@
  $tmp = Join-Path $env:TEMP 'frankie_diag_ssm.py'; Set-Content -Path $tmp -Value $code -Encoding ASCII
  & $py $tmp
  Remove-Item $tmp -ErrorAction SilentlyContinue
} else { Write-Output "skipped (no source or host python missing)" }
Write-Output "### done"
