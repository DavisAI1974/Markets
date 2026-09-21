# Record Root's actual Frankie response on the native host (2026-09-20 20:55Z).
#
# Why: Root ran operations/record_actual_frankie_response.py on his own machine, but the recorder
# writes into the retained run directory under the run's lock, so the record must be made ON the
# host. This delivers Root's three files (the response, the host attestation, the host session
# record the attestation pins) from a presigned staging (URLs signed and masked by the workflow,
# never printed here), verifies each by sha256 and bytes, places the session record where the
# attestation says it lives (derived from the configuration's run directory; the attestation's
# host_record.path must name exactly that file), runs the recorder from the host tools checkout,
# and writes one receipt into the day directory. Nothing is deleted or written over: an existing
# session-response.json is reported and left alone, an existing session record with different
# bytes refuses. $Day, $RunRoot, $ToolsRoot, $Python, $CycleIndex, the three Url/Sha256/Bytes triples
# and $SourceRef arrive from ssm_run_ps1.py --set; no path literal here.
$ErrorActionPreference = 'Stop'
foreach ($required in 'Day', 'RunRoot', 'ToolsRoot', 'Python', 'CycleIndex', 'SourceRef',
        'ResponseUrl', 'ResponseSha256', 'ResponseBytes',
        'AttestationUrl', 'AttestationSha256', 'AttestationBytes',
        'RecordUrl', 'RecordSha256', 'RecordBytes') {
    $value = Get-Variable -Name $required -ValueOnly -ErrorAction SilentlyContinue
    if (-not $value -or $value -like 'HOST_*') { throw "$required was not supplied by ssm_run_ps1.py --set (value: '$value')" }
}
if ($CycleIndex -notmatch '^\d{2}$') { throw "CycleIndex must be two digits (value: '$CycleIndex')" }
foreach ($name in 'ResponseSha256', 'AttestationSha256', 'RecordSha256') {
    if ((Get-Variable -Name $name -ValueOnly) -notmatch '^[0-9a-f]{64}$') { throw "$name must be 64 lowercase hex" }
}
foreach ($name in 'ResponseBytes', 'AttestationBytes', 'RecordBytes') {
    if ((Get-Variable -Name $name -ValueOnly) -notmatch '^\d+$') { throw "$name must be digits" }
}
$dayDirectory = Join-Path $RunRoot $Day
$cfgPath = Join-Path $dayDirectory 'actual-host-configuration.json'
if (-not (Test-Path $cfgPath)) { throw "no run configuration for $Day at $cfgPath" }
$cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
$sha = [System.Security.Cryptography.SHA256]::Create()
function Digest([string]$path) { ([BitConverter]::ToString($script:sha.ComputeHash([IO.File]::ReadAllBytes($path)))).Replace('-', '').ToLower() }
function Normal([string]$path) { ($path -replace '\\', '/').TrimEnd('/').ToLowerInvariant() }
$cfgSha = Digest $cfgPath
$run = $cfg.run_directory
if (-not $run -or -not (Test-Path $run)) { throw ("run directory absent: " + $run) }
$principal = Join-Path (Join-Path (Join-Path $run 'execution') ('cycle-' + $CycleIndex)) 'principal'
$requestPath = Join-Path $principal 'session-request.json'
$responsePath = Join-Path $principal 'session-response.json'
if (-not (Test-Path $requestPath)) { throw ("no durable principal request for cycle " + $CycleIndex + " at " + $requestPath + "; recording cannot precede it") }
Write-Output ("configuration " + $cfgPath + " sha256=" + $cfgSha)
Write-Output ("principal directory " + $principal)
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
if (Test-Path $responsePath) {
    Write-Output ("ALREADY_RECORDED session-response.json present, bytes=" + (Get-Item $responsePath).Length + " sha256=" + (Digest $responsePath) + "; nothing written")
    exit 0
}
$incoming = Join-Path $principal ('incoming-' + $stamp)
if (Test-Path $incoming) { throw ("incoming path already exists: " + $incoming) }
New-Item -ItemType Directory -Path $incoming | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
function Fetch([string]$url, [string]$target, [string]$expectedSha, [string]$expectedBytes, [string]$label) {
    $previous = $ProgressPreference; $ProgressPreference = 'SilentlyContinue'
    try { Invoke-WebRequest -Uri $url -OutFile $target -UseBasicParsing } finally { $ProgressPreference = $previous }
    if (-not (Test-Path $target)) { throw ($label + ': download produced no file') }
    $got = Get-Item $target
    $gotDigest = Digest $target
    if ($got.Length -ne [int64]$expectedBytes -or $gotDigest -ne $expectedSha) {
        throw ($label + " differs from the declaration (" + $got.Length + " bytes, sha256 " + $gotDigest + " vs " + $expectedBytes + " " + $expectedSha + "); left in " + $incoming)
    }
    Write-Output ("delivered " + $label + " bytes=" + $got.Length + " sha256=" + $gotDigest)
}
$responseFile = Join-Path $incoming 'response.json'
$attestationFile = Join-Path $incoming 'host-attestation.json'
$recordFile = Join-Path $incoming 'host-session-record.json'
Fetch $ResponseUrl $responseFile $ResponseSha256 $ResponseBytes 'response'
Fetch $AttestationUrl $attestationFile $AttestationSha256 $AttestationBytes 'host attestation'
Fetch $RecordUrl $recordFile $RecordSha256 $RecordBytes 'host session record'
# The attestation pins the session record by path, bytes and sha256; the recorder reads that path on
# THIS machine, so the record is placed beside the request and the attestation must name that file.
$attestation = Get-Content $attestationFile -Raw | ConvertFrom-Json
$recordTarget = Join-Path $principal 'host-session-record.json'
$pinned = $attestation.host_record
if (-not $pinned -or -not $pinned.path -or -not $pinned.sha256) { throw 'the attestation carries no host_record {path, bytes, sha256}' }
$attestationPathRewrittenFrom = $null
if ((Normal $pinned.path) -ne (Normal $recordTarget)) {
    # Greg, 2026-09-20 21:05Z: this provenance gate is overridden with a receipt. Root produced the
    # attestation on his own machine, so host_record.path names a file there; what the pin verifies is
    # the record's bytes and sha256, and those are checked below unchanged. Only the path is rewritten,
    # to where the record is placed on this host, into a NEW file; Root's original stays untouched in
    # the incoming directory and the original value goes into the receipt.
    $attestationPathRewrittenFrom = [string]$pinned.path
    $attestation.host_record.path = $recordTarget
    $attestationFile = Join-Path $incoming 'host-attestation.host-path.json'
    Set-Content -Path $attestationFile -Value ($attestation | ConvertTo-Json -Depth 12) -NoNewline -Encoding UTF8
    $AttestationSha256 = Digest $attestationFile
    $AttestationBytes = [string](Get-Item $attestationFile).Length
    $pinned = $attestation.host_record
    Write-Output ("attestation host_record.path rewritten from '" + $attestationPathRewrittenFrom + "' to the host path (receipted); rewritten file sha256=" + $AttestationSha256 + " bytes=" + $AttestationBytes)
}
if ($pinned.sha256 -ne $RecordSha256 -or [int64]$pinned.bytes -ne [int64]$RecordBytes) {
    throw ("refusing: the attestation pins the record as " + $pinned.bytes + " bytes sha256 " + $pinned.sha256 + "; the delivered record is " + $RecordBytes + " " + $RecordSha256)
}
if (Test-Path $recordTarget) {
    if ((Digest $recordTarget) -ne $RecordSha256) { throw ("refusing: a different host-session-record.json is present at " + $recordTarget + " (sha256 " + (Digest $recordTarget) + "); not replaced") }
    Write-Output 'host session record already in place with the pinned digest'
} else {
    Copy-Item -LiteralPath $recordFile -Destination $recordTarget
    if ((Digest $recordTarget) -ne $RecordSha256) { throw 'host session record digest changed on placement' }
    Write-Output ("placed host session record at " + $recordTarget)
}
$tool = Join-Path $ToolsRoot 'research\kalshi\frankie_boss\operations\record_actual_frankie_response.py'
if (-not (Test-Path $tool)) { throw ("recorder missing from the tools checkout: " + $tool) }
if (-not (Test-Path $Python)) { throw ("host python missing: " + $Python) }
$git = Get-Command git -ErrorAction SilentlyContinue
$toolsHead = if ($git) { (& $git.Source -C $ToolsRoot rev-parse HEAD) } else { 'unknown' }
Write-Output ("TOOLS_HEAD=" + $toolsHead)
$log = Join-Path $dayDirectory ('principal-response-recorder-' + $stamp + '.log')
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = $ToolsRoot
$env:PYTHONIOENCODING = 'utf-8'
# The recorder's own __main__ prints only {"status": "refused", "error_type": ...} and swallows the message (run
# 35630974458, 2026-09-21: a ValueError with no text). This wrapper, sent with the script from the dispatched ref,
# runs the same main() from the host tools checkout and, on a refusal, prints the traceback and the message too.
$wrapper = @'
import importlib.util, json, sys, traceback
tool = sys.argv[1]
sys.argv = [tool] + sys.argv[2:]
spec = importlib.util.spec_from_file_location('record_actual_frankie_response', tool)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
try:
    module.main()
except SystemExit:
    raise
except Exception as error:
    traceback.print_exc(file=sys.stdout)      # stdout: under Stop, the first stderr line would end the host script early (run 35631652890)
    print(json.dumps(dict(status='refused', error_type=type(error).__name__, error=str(error)[:800])))
    sys.stdout.flush()
    raise SystemExit(1)
'@
Push-Location $ToolsRoot
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'   # a line on stderr from the recorder is output to keep, not a terminating error
try {
    & $Python -c $wrapper $tool --configuration $cfgPath --configuration-sha256 $cfgSha --cycle-index ([int]$CycleIndex) `
        --response $responseFile --response-sha256 $ResponseSha256 `
        --host-attestation $attestationFile --host-attestation-sha256 $AttestationSha256 2>&1 | ForEach-Object { $_.ToString() } | Tee-Object -FilePath $log
    $recorderExit = $LASTEXITCODE
} finally { Pop-Location; $ErrorActionPreference = $previousPreference }
$output = if (Test-Path $log) { Get-Content $log -Raw } else { '' }
if ($recorderExit -ne 0 -or $output -notmatch 'actual_principal_response_recorded') {
    throw ("the recorder did not record (exit " + $recorderExit + "); its output is above and in " + $log)
}
if (-not (Test-Path $responsePath)) { throw 'the recorder reported success but session-response.json is absent' }
$statusLine = ($output -split "`n" | Where-Object { $_ -match 'actual_principal_response_recorded' } | Select-Object -Last 1).Trim()
$receipt = [ordered]@{
    schema                  = 'FRANKIE_PRINCIPAL_RESPONSE_RECORDED_V1'
    day                     = $Day
    run_id                  = $cfg.run_id
    cycle_index             = [int]$CycleIndex
    source_ref              = $SourceRef
    tools_head              = $toolsHead
    configuration_sha256    = $cfgSha
    response_sha256         = $ResponseSha256
    response_bytes          = [int64]$ResponseBytes
    host_attestation_sha256 = $AttestationSha256
    host_attestation_bytes  = [int64]$AttestationBytes
    host_attestation_path_rewritten_from = $attestationPathRewrittenFrom
    host_record_path        = $recordTarget
    host_record_sha256      = $RecordSha256
    host_record_bytes       = [int64]$RecordBytes
    session_response_path   = $responsePath
    session_response_sha256 = (Digest $responsePath)
    session_response_bytes  = (Get-Item $responsePath).Length
    recorder_status         = $statusLine
    incoming_directory      = $incoming
    at                      = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
}
$receiptPath = Join-Path $dayDirectory ('principal-response-recorded-' + $stamp + '.json')
Set-Content -Path $receiptPath -Value ($receipt | ConvertTo-Json -Depth 4) -NoNewline -Encoding UTF8
Write-Output ("receipt: " + $receiptPath)
Write-Output ('RECEIPT ' + ($receipt | ConvertTo-Json -Depth 4 -Compress))
