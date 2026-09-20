# Bring the native host's tools checkout up to the declared frozen native runtime (96e26f7d), which
# carries the request-id fix c0749bc0 that the host's c9a86e74 lacks, and record the new boss_commit
# in the sealed host configuration. Refuses on a dirty tree. Keeps a dated backup of the configuration.
# Writes only the checkout and that one configuration field. Starts nothing.
$ErrorActionPreference = 'Stop'
$tools = 'C:/tools/Frankie-20260919/Markets'
$cfg = 'C:/Codex/Frankie-BOSS-20260919/days/20211003/actual-host-configuration.json'
$target = '96e26f7d5e8100cca93288d5f44d9550ab5cfd9a'
$git = (Get-Command git -ErrorAction Stop).Source
if (-not (Test-Path $tools)) { throw "tools checkout missing: $tools" }
$dirty = & $git -C $tools status --porcelain
if ($dirty) { throw ("refusing: tools checkout is dirty:`n" + ($dirty -join "`n")) }
$before = (& $git -C $tools rev-parse HEAD).Trim()
Write-Output ("before: " + $before)
& $git -C $tools fetch -q origin $target
if ($LASTEXITCODE -ne 0) { throw 'fetch of the frozen runtime commit failed' }
& $git -C $tools checkout -q --detach $target
if ($LASTEXITCODE -ne 0) { throw 'checkout of the frozen runtime commit failed' }
$after = (& $git -C $tools rev-parse HEAD).Trim()
if ($after -ne $target) { throw ("checkout landed on " + $after) }
Write-Output ("after:  " + $after)
$ras = Join-Path $tools 'research/kalshi/frankie_boss/operations/run_actual_sunday.py'
$fix = (Select-String -Path $ras -SimpleMatch 'cycle-{index:02d}' | Measure-Object).Count
if ($fix -lt 2) { throw 'advanced checkout still lacks the request-id fix' }
Write-Output ("run_actual_sunday.py carries the cycle request-id fix (occurrences=" + $fix + ")")
$raw = Get-Content $cfg -Raw
$backup = $cfg + '.before-advance-' + (Get-Date -Format 'yyyyMMddTHHmmssZ') + '.json'
Set-Content -Path $backup -Value $raw -NoNewline -Encoding UTF8
$c = $raw | ConvertFrom-Json
$oldBoss = $c.host_runtime.boss_commit
if ($oldBoss -ne $before) { throw ("configuration boss_commit " + $oldBoss + " does not match the checkout that was just replaced " + $before) }
# Replace only the boss_commit value, textually, so every other byte of the sealed file is untouched.
$pattern = '"boss_commit":\s*"' + [regex]::Escape($oldBoss) + '"'
if (([regex]::Matches($raw, $pattern)).Count -ne 1) { throw 'boss_commit field not found exactly once' }
$updated = [regex]::Replace($raw, $pattern, '"boss_commit": "' + $target + '"', 1)
Set-Content -Path $cfg -Value $updated -NoNewline -Encoding UTF8
$check = (Get-Content $cfg -Raw | ConvertFrom-Json).host_runtime.boss_commit
if ($check -ne $target) { throw 'boss_commit did not update' }
Write-Output ('RECEIPT ' + (@{schema='FRANKIE_HOST_ADVANCE_RECEIPT_V1'; tools=$tools; before=$before; after=$after; boss_commit_before=$oldBoss; boss_commit_after=$target; configuration_backup=$backup; at=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()} | ConvertTo-Json -Compress))
