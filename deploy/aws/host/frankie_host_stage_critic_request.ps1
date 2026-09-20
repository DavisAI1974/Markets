# Stage one cycle's minted Granite critic request off the native host (2026-09-20 23:30Z).
#
# Why: the retained Granite observer (granite_retained_host.prepare) admits a request only from its
# authenticated Git archive (runs/request-archives/<sha>/) or the retained S3 request prefix, and the
# repository has no writer for either (MASTER_WEAVE_20260920.md, fact 2). A whole-cycle rerun mints a
# NEW critic request, so the request must be published before any observer can prepare readiness for
# it. This uploads exactly execution/cycle-NN/actual-critic-request.json, unchanged, through a presigned
# PUT the workflow signed and masked (never printed here), prints its bytes and sha256, and writes one
# receipt in the day directory. Reads only on the host. The credential is never opened. $Day, $RunRoot,
# $CycleIndex and $RequestUrl arrive from ssm_run_ps1.py --set; no path literal here.
$ErrorActionPreference = 'Stop'
foreach ($required in 'Day', 'RunRoot', 'CycleIndex', 'RequestUrl') {
    $value = Get-Variable -Name $required -ValueOnly -ErrorAction SilentlyContinue
    if (-not $value -or $value -like 'HOST_*') { throw "$required was not supplied by ssm_run_ps1.py --set (value: '$value')" }
}
if ($CycleIndex -notmatch '^\d{2}$') { throw "CycleIndex must be two digits (value: '$CycleIndex')" }
$dayDirectory = Join-Path $RunRoot $Day
$cfgPath = Join-Path $dayDirectory 'actual-host-configuration.json'
if (-not (Test-Path $cfgPath)) { throw "no run configuration for $Day at $cfgPath" }
$cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
$sha = [System.Security.Cryptography.SHA256]::Create()
function Digest([string]$path) { ([BitConverter]::ToString($script:sha.ComputeHash([IO.File]::ReadAllBytes($path)))).Replace('-', '').ToLower() }
$run = $cfg.run_directory
if (-not $run -or -not (Test-Path $run)) { throw ("run directory absent: " + $run) }
$cycle = Join-Path (Join-Path $run 'execution') ('cycle-' + $CycleIndex)
$name = 'actual-critic-request.json'
$path = Join-Path $cycle $name
if (-not (Test-Path $path)) { throw ("minted critic request absent: " + $path) }
$bytes = (Get-Item $path).Length
$digest = Digest $path
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$previous = $ProgressPreference; $ProgressPreference = 'SilentlyContinue'
try { Invoke-WebRequest -Uri $RequestUrl -Method Put -InFile $path -UseBasicParsing | Out-Null }
catch {
    $detail = ''
    try { $detail = (New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())).ReadToEnd() -replace '<RequestId>.*?</RequestId>', '' -replace '<HostId>.*?</HostId>', '' }
    catch { $detail = $_.Exception.Message }
    throw ("upload of " + $name + " refused: " + $_.Exception.Message + " " + $detail)
}
finally { $ProgressPreference = $previous }
Write-Output ("EXPORTED " + $name + " bytes=" + $bytes + " sha256=" + $digest)
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$receipt = [ordered]@{
    schema      = 'FRANKIE_CRITIC_REQUEST_STAGED_V1'
    day         = $Day
    run_id      = $cfg.run_id
    cycle_index = [int]$CycleIndex
    path        = $path
    bytes       = $bytes
    sha256      = $digest
    reason      = 'the retained Granite observer admits a request only from its Git archive or the S3 request prefix; a whole-cycle rerun minted a new request, published here unchanged and verified by sha256 on both ends'
    at          = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
}
$receiptPath = Join-Path $dayDirectory ('critic-request-staged-' + $stamp + '.json')
[IO.File]::WriteAllText($receiptPath, ($receipt | ConvertTo-Json -Depth 6 -Compress), (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("receipt: " + $receiptPath)
