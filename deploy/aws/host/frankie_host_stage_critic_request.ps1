# Export one exact minted critic request through a caller-supplied private PUT.
# Source JSON bytes are never parsed or rewritten. A create-new flushed intent
# precedes HTTP; a distinct completion follows successful upload and source recheck.
# The archive workflow separately verifies the received object against this pin.
# Day, RunRoot, CycleIndex, ExpectedRequestSha256 and RequestUrl arrive via --set.
$ErrorActionPreference = 'Stop'

function Assert-ExportPath([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    $cursor = $full
    while ($cursor) {
        $item = Get-Item -LiteralPath $cursor -Force -ErrorAction SilentlyContinue
        if ($item -and ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'critic export refuses a reparse path'
        }
        $parent = [IO.Path]::GetDirectoryName($cursor)
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
    return $full
}

function Get-ExportWitness([string]$Path) {
    $full = Assert-ExportPath $Path
    $item = Get-Item -LiteralPath $full -Force -ErrorAction Stop
    if ($item.PSIsContainer) { throw 'critic export requires a regular file' }
    $stream = [IO.File]::OpenRead($full)
    $hasher = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = $stream.Length
        $digest = ([BitConverter]::ToString($hasher.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
        if ($stream.Length -ne $bytes) { throw 'critic export file changed while hashing' }
        return [ordered]@{ bytes = $bytes; sha256 = $digest }
    } finally { $stream.Dispose(); $hasher.Dispose() }
}

function Write-ExportJson([string]$Path, $Value) {
    $full = Assert-ExportPath $Path
    $pending = Assert-ExportPath ($full + '.pending-' + [Guid]::NewGuid().ToString('N'))
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes((ConvertTo-Json -InputObject $Value -Depth 8 -Compress))
    $stream = [IO.File]::Open($pending, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
    $null = Assert-ExportPath $full
    $null = Assert-ExportPath $pending
    # Atomic publish refuses an existing name. Partial files remain for diagnosis.
    [IO.File]::Move($pending, $full)
}

foreach ($required in 'Day', 'RunRoot', 'CycleIndex', 'ExpectedRequestSha256', 'RequestUrl') {
    $value = Get-Variable -Name $required -ValueOnly -ErrorAction SilentlyContinue
    if (-not $value -or $value -like 'HOST_*') {
        # Never include the value: RequestUrl carries a signed capability.
        throw ($required + ' was not supplied by ssm_run_ps1.py --set')
    }
}
if ($Day -notmatch '^\d{8}$') { throw 'Day must be an eight-digit trading date' }
if ($CycleIndex -notmatch '^\d{2}$') { throw 'CycleIndex must be two digits' }
if ($ExpectedRequestSha256 -cnotmatch '^[0-9a-f]{64}$') { throw 'ExpectedRequestSha256 must be 64 lowercase hex digits' }
if (-not [IO.Path]::IsPathRooted($RunRoot)) { throw 'RunRoot must be absolute' }
$uploadUri = $null
if (-not [Uri]::TryCreate([string]$RequestUrl, [UriKind]::Absolute, [ref]$uploadUri) -or
    $uploadUri.Scheme -cne 'https' -or $uploadUri.UserInfo -or $uploadUri.Fragment) {
    throw 'a private HTTPS upload capability is required'
}

$dayDirectory = Assert-ExportPath (Join-Path $RunRoot $Day)
$cfgPath = Assert-ExportPath (Join-Path $dayDirectory 'actual-host-configuration.json')
$configuration = Get-ExportWitness $cfgPath
$cfg = Get-Content -LiteralPath $cfgPath -Encoding UTF8 -Raw | ConvertFrom-Json
if ($cfg.run_id -isnot [string] -or [string]::IsNullOrWhiteSpace($cfg.run_id) -or
    $cfg.run_directory -isnot [string] -or -not [IO.Path]::IsPathRooted($cfg.run_directory)) {
    throw 'critic export requires a configured run identity and absolute directory'
}
$run = Assert-ExportPath $cfg.run_directory
if (-not (Test-Path -LiteralPath $run -PathType Container)) { throw 'configured run directory absent' }
$cycle = Assert-ExportPath (Join-Path (Join-Path $run 'execution') ('cycle-' + $CycleIndex))
$name = 'actual-critic-request.json'
$path = Assert-ExportPath (Join-Path $cycle $name)
$witness = Get-ExportWitness $path
if ($witness.sha256 -cne $ExpectedRequestSha256) {
    throw 'minted critic request differs from ExpectedRequestSha256; nothing uploaded'
}
if ((Get-ExportWitness $cfgPath).sha256 -cne $configuration.sha256) {
    throw 'configuration changed before critic export'
}

$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ') + '-' + [Guid]::NewGuid().ToString('N')
$stem = Join-Path $dayDirectory ('critic-request-staged-' + $stamp)
$intentPath = $stem + '.intent.json'
$intent = [ordered]@{
    schema = 'FRANKIE_CRITIC_REQUEST_STAGE_INTENT_V1'
    day = $Day
    run_id = $cfg.run_id
    run_directory = $run
    cycle_index = [int]$CycleIndex
    path = $path
    bytes = $witness.bytes
    sha256 = $witness.sha256
    configuration_sha256 = $configuration.sha256
    at = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
}
Write-ExportJson $intentPath $intent
$intentWitness = Get-ExportWitness $intentPath
$null = Assert-ExportPath $path
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$previous = $ProgressPreference
$ProgressPreference = 'SilentlyContinue'
try {
    Invoke-WebRequest -Uri $RequestUrl -Method Put -InFile $path -UseBasicParsing | Out-Null
} catch {
    # Remote exception text and response bodies can contain signed URL material.
    throw 'critic request upload failed; durable intent retained'
} finally { $ProgressPreference = $previous }

$after = Get-ExportWitness $path
if ($after.bytes -ne $witness.bytes -or $after.sha256 -cne $witness.sha256 -or
    (Get-ExportWitness $cfgPath).sha256 -cne $configuration.sha256) {
    throw 'critic export source or configuration changed; intent retained without completion'
}
$receipt = [ordered]@{
    schema = 'FRANKIE_CRITIC_REQUEST_STAGED_V1'
    day = $Day
    run_id = $cfg.run_id
    cycle_index = [int]$CycleIndex
    path = $path
    bytes = $witness.bytes
    sha256 = $witness.sha256
    configuration_sha256 = $configuration.sha256
    intent_path = $intentPath
    intent_sha256 = $intentWitness.sha256
    reason = 'upload returned successfully and source bytes were rechecked; archive caller must verify the received object'
    at = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
}
$receiptPath = $stem + '.json'
Write-ExportJson $receiptPath $receipt
Write-Output ('EXPORTED ' + $name + ' bytes=' + $witness.bytes + ' sha256=' + $witness.sha256)
Write-Output ('receipt: ' + $receiptPath)
