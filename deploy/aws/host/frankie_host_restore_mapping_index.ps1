# Restore the source mapping index (index.jsonl) beside the retained mapping.json (2026-09-20).
#
# Why: pipeline run 35520104563 stopped inside cycle 0's causal handoff with FileNotFoundError at
# frankie_source_mapping.py:242 (_plain(directory/'index.jsonl')). The 20260915 restoration package
# carried mapping/mapping.json (1,063 bytes) and execution/cycle-00/principal/bound-mapping.json but
# never index.jsonl (16,121,079 bytes), so every earlier host run skipped bind_prefix on the retained
# binding and this run, the first to bind on this host, had nothing to read. mapping.json pins the
# index by byte count and sha256; frankie_boss_ledger_mapping.yml rebuilt it from the preserved S3
# source and member ledger, and the delivery workflow verified it against that pin before staging it
# on S3. This script places it only after re-verifying the same pin off the host's own mapping.json.
#
# NOTHING IS DELETED. An index already present with the pinned digest is left alone (receipt says
# so); a different one is refused, not replaced. A download that fails the pin is moved into
# <RunRoot parent>/superseded/ and the script throws. Starts, stops and dispatches nothing; never
# reads the SSM credential parameter; the host role's own S3 access performs the download.
#
# $Day, $RunRoot, $Python, $Bucket, $Key, $ExpectedSha256, $ExpectedBytes arrive from
# ssm_run_ps1.py --set; no path literal here.
$ErrorActionPreference = 'Stop'
foreach ($required in 'Day', 'RunRoot', 'Python', 'Bucket', 'Key', 'ExpectedSha256', 'ExpectedBytes') {
    $value = Get-Variable -Name $required -ValueOnly -ErrorAction SilentlyContinue
    if (-not $value -or $value -like 'HOST_*') { throw "$required was not supplied by ssm_run_ps1.py --set (value: '$value')" }
}
if ($ExpectedSha256 -notmatch '^[0-9a-f]{64}$') { throw "ExpectedSha256 must be 64 lowercase hex (value: '$ExpectedSha256')" }
if ($ExpectedBytes -notmatch '^\d+$') { throw "ExpectedBytes must be digits (value: '$ExpectedBytes')" }
$dayDirectory = Join-Path $RunRoot $Day
$cfgPath = Join-Path $dayDirectory 'actual-host-configuration.json'
if (-not (Test-Path $cfgPath)) { throw "no run configuration for $Day at $cfgPath" }
$cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
if (-not (Test-Path $Python)) { throw "host python missing: $Python" }
$sha = [System.Security.Cryptography.SHA256]::Create()
function Digest([string]$path) { ([BitConverter]::ToString($script:sha.ComputeHash([IO.File]::ReadAllBytes($path)))).Replace('-', '').ToLower() }

$mappingPath = $cfg.mapping.path
if (-not $mappingPath -or -not (Test-Path $mappingPath)) { throw ("retained mapping.json absent: " + $mappingPath) }
$mappingDigest = Digest $mappingPath
if ($mappingDigest -ne $cfg.mapping.sha256) { throw ("refusing: mapping.json digest " + $mappingDigest + " differs from the configuration pin " + $cfg.mapping.sha256) }
$mapping = Get-Content $mappingPath -Raw | ConvertFrom-Json
$pin = $mapping.index
if ($pin.path -ne 'index.jsonl' -or $pin.sha256 -ne $ExpectedSha256 -or [int64]$pin.bytes -ne [int64]$ExpectedBytes) {
    throw ("refusing: mapping.json pins index " + $pin.path + " " + $pin.bytes + " " + $pin.sha256 + "; the delivery declares " + $ExpectedBytes + " " + $ExpectedSha256)
}
$mappingDirectory = Split-Path $mappingPath -Parent
$target = Join-Path $mappingDirectory $pin.path
Write-Output ("mapping.json " + $mappingPath + " sha256=" + $mappingDigest)
Write-Output ("index target " + $target)
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$status = $null
if (Test-Path $target) {
    $present = Get-Item $target
    $presentDigest = Digest $target
    if ($presentDigest -eq $pin.sha256 -and $present.Length -eq [int64]$pin.bytes) {
        Write-Output "index.jsonl already present with the pinned digest; nothing written"
        $status = 'already_present'
    } else {
        throw ("refusing: a different index.jsonl is present (" + $present.Length + " bytes, sha256 " + $presentDigest + "); not replaced")
    }
} else {
    $incoming = Join-Path $mappingDirectory ('index.jsonl.incoming-' + $stamp)
    if (Test-Path $incoming) { throw ("incoming path already exists: " + $incoming) }
    Write-Output ("downloading s3://" + $Bucket + "/" + $Key + " with the host role")
    # Every string reaches python through argv: Windows PowerShell strips inner double quotes from a
    # native command's arguments (run 35522551415: NameError 's3'), so the one-liner carries none.
    & $Python -c 'import boto3, sys; boto3.client(sys.argv[1], region_name=sys.argv[2]).download_file(sys.argv[3], sys.argv[4], sys.argv[5])' s3 us-east-1 $Bucket $Key $incoming
    if ($LASTEXITCODE -ne 0) { throw ("download failed with exit code " + $LASTEXITCODE) }
    $got = Get-Item $incoming
    $gotDigest = Digest $incoming
    if ($got.Length -ne [int64]$pin.bytes -or $gotDigest -ne $pin.sha256) {
        $aside = Join-Path (Join-Path (Split-Path $RunRoot -Parent) 'superseded') ('mapping-index-rejected-' + $stamp)
        New-Item -ItemType Directory -Force -Path $aside | Out-Null
        Move-Item -LiteralPath $incoming -Destination (Join-Path $aside 'index.jsonl')
        throw ("downloaded index differs from the pin (" + $got.Length + " bytes, sha256 " + $gotDigest + "); moved to " + $aside)
    }
    Move-Item -LiteralPath $incoming -Destination $target
    if (Test-Path $incoming) { throw 'rename left the incoming file in place' }
    if ((Digest $target) -ne $pin.sha256) { throw 'index.jsonl digest changed after the rename' }
    Write-Output ("placed index.jsonl  bytes=" + $pin.bytes + "  sha256=" + $pin.sha256)
    $status = 'placed'
}
$receipt = [ordered]@{
    schema         = 'FRANKIE_MAPPING_INDEX_RESTORED_V1'
    day            = $Day
    run_id         = $cfg.run_id
    status         = $status
    mapping_path   = $mappingPath
    mapping_sha256 = $mappingDigest
    index_path     = $target
    index_bytes    = [int64]$pin.bytes
    index_sha256   = $pin.sha256
    source         = 's3://' + $Bucket + '/' + $Key
    reason         = 'pipeline run 35520104563 stopped at frankie_source_mapping.py:242 (FileNotFoundError); the restoration package never carried index.jsonl; rebuilt by frankie_boss_ledger_mapping.yml and verified against the mapping.json pin'
    at             = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
}
$receiptPath = Join-Path $dayDirectory ('mapping-index-restored-' + $stamp + '.json')
Set-Content -Path $receiptPath -Value ($receipt | ConvertTo-Json -Depth 4) -NoNewline -Encoding UTF8
Write-Output ("receipt: " + $receiptPath)
Write-Output ('RECEIPT ' + ($receipt | ConvertTo-Json -Depth 4 -Compress))
