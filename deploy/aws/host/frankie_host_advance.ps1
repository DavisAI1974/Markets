# Bring the native host's tools checkout to an explicit commit ($Target, a full 40-hex sha supplied by
# ssm_run_ps1.py --set; never hardcoded here) and record it as boss_commit in the sealed host
# configuration. First use (2026-09-20): 96e26f7d, the frozen native runtime carrying the request-id
# fix. Second use: the re-minted retained Pod identity, because verified_service_inputs builds the
# Runpod config from the checkout's POD_ID. Refuses on a dirty tree, refuses a target that is not a
# descendant of the current checkout, keeps a dated backup of the configuration, writes only the
# checkout and that one field. Starts nothing.
$ErrorActionPreference = 'Stop'
if (-not $Target -or $Target -notmatch '^[0-9a-f]{40}$') { throw 'Target (full 40-hex commit) must be supplied with --set Target=<sha>' }
$tools = 'C:/tools/Frankie-20260919/Markets'
$cfg = 'C:/Codex/Frankie-BOSS-20260919/days/20211003/actual-host-configuration.json'
$target = $Target
$git = (Get-Command git -ErrorAction Stop).Source
if (-not (Test-Path $tools)) { throw "tools checkout missing: $tools" }
$dirty = & $git -C $tools status --porcelain
if ($dirty) { throw ("refusing: tools checkout is dirty:`n" + ($dirty -join "`n")) }
$before = (& $git -C $tools rev-parse HEAD).Trim()
Write-Output ("before: " + $before)
& $git -C $tools fetch -q origin $target
if ($LASTEXITCODE -ne 0) { throw 'fetch of the target commit failed' }
& $git -C $tools merge-base --is-ancestor $before $target
if ($LASTEXITCODE -ne 0) { throw ("refusing: target " + $target + " does not descend from the current checkout " + $before) }
& $git -C $tools checkout -q --detach $target
if ($LASTEXITCODE -ne 0) { throw 'checkout of the target commit failed' }
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
