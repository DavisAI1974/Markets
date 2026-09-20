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
