# Export the retained principal request materials of one cycle from the native host (2026-09-20 21:40Z).
#
# Why: Root's Frankie session runs on Greg's box and cannot see the host, so it never had the durable
# request. The request lives only in the retained run directory: principal/session-request.json,
# principal/prompt.md and principal/historical-prompt.md. This uploads exactly those three files,
# unchanged, through presigned PUTs the workflow signed and masked (never printed here), and prints
# each file's bytes and sha256 so Root verifies what he downloads. Reads only, plus one receipt in the
# day directory. The credential is never opened. $Day, $RunRoot, $CycleIndex and the three Url values
# arrive from ssm_run_ps1.py --set; no path literal here.
$ErrorActionPreference = 'Stop'
foreach ($required in 'Day', 'RunRoot', 'CycleIndex', 'RequestUrl', 'PromptUrl', 'HistoricalUrl') {
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
$principal = Join-Path (Join-Path (Join-Path $run 'execution') ('cycle-' + $CycleIndex)) 'principal'
$files = [ordered]@{
    'session-request.json' = $RequestUrl
    'prompt.md'            = $PromptUrl
    'historical-prompt.md' = $HistoricalUrl
}
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$exported = [ordered]@{}
foreach ($name in $files.Keys) {
    $path = Join-Path $principal $name
    if (-not (Test-Path $path)) { throw ("retained principal file absent: " + $path) }
    $bytes = (Get-Item $path).Length
    $digest = Digest $path
    $previous = $ProgressPreference; $ProgressPreference = 'SilentlyContinue'
    try { Invoke-WebRequest -Uri $files[$name] -Method Put -InFile $path -UseBasicParsing | Out-Null }
    catch {
        $detail = ''
        try { $detail = (New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())).ReadToEnd() -replace '<RequestId>.*?</RequestId>', '' -replace '<HostId>.*?</HostId>', '' }
        catch { $detail = $_.Exception.Message }
        throw ("upload of " + $name + " refused: " + $_.Exception.Message + " " + $detail)
    }
    finally { $ProgressPreference = $previous }
    Write-Output ("EXPORTED " + $name + " bytes=" + $bytes + " sha256=" + $digest)
    $exported[$name] = [ordered]@{ bytes = $bytes; sha256 = $digest }
}
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$receipt = [ordered]@{
    schema      = 'FRANKIE_PRINCIPAL_REQUEST_EXPORTED_V1'
    day         = $Day
    run_id      = $cfg.run_id
    cycle_index = [int]$CycleIndex
    principal   = $principal
    files       = $exported
    reason      = 'Root performs the Frankie session off the host and needs the durable request and prompt; content unchanged, verified by sha256 on both ends'
    at          = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
}
$receiptPath = Join-Path $dayDirectory ('principal-request-exported-' + $stamp + '.json')
Set-Content -Path $receiptPath -Value ($receipt | ConvertTo-Json -Depth 5) -NoNewline -Encoding UTF8
Write-Output ("receipt: " + $receiptPath)
Write-Output ('RECEIPT ' + ($receipt | ConvertTo-Json -Depth 5 -Compress))
