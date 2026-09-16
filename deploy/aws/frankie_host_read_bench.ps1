$ErrorActionPreference = 'Continue'
# Read back the benchmark and profile results from E:\bench in a compact form for the session record.
foreach ($t in @(8, 16)) {
    $f = "E:\bench\direct_${t}t.jsonl"
    if (Test-Path $f) {
        Write-Output "=== direct_${t}t.jsonl"
        Get-Content $f | Where-Object { $_ -match '"stage": "(driver_start|host_class|source_verified|prefix_verified|fresh_checkpoint_ready|feedback_verified|learner_step_start|learner\.[a-z_]+|learner_step_complete|driver_failed|driver_end)"' } | ForEach-Object { $_.Substring(0, [Math]::Min(420, $_.Length)) }
    } else { Write-Output "=== direct_${t}t.jsonl ABSENT" }
}
foreach ($p in @('profile_prefix01_compact.json', 'profile_prefix00_raw.json')) {
    $f = "E:\bench\$p"
    if (Test-Path $f) {
        $r = Get-Content $f -Raw | ConvertFrom-Json
        foreach ($run in $r.runs) { Write-Output ("PROFILE " + $p + " " + $run.label + " wall=" + $run.wall_seconds + "s rows=" + $run.rows + " ms_per_row=" + $run.ms_per_row) }
    }
}
if (Test-Path E:\bench\compact-source-verify-scratch\compact-source-verification.json) {
    $v = Get-Content E:\bench\compact-source-verify-scratch\compact-source-verification.json -Raw | ConvertFrom-Json
    Write-Output ("COMPACT_PROOF source_seconds=" + $v.source_seconds + " total_seconds=" + $v.total_seconds + " cycles=" + $v.cycles.Count + " blocks_decoded=" + $v.compact.blocks)
    foreach ($c in $v.cycles) { Write-Output ("  cycle " + $c.cycle_index + " count=" + $c.source_checkpoint.count + " blocks=" + $c.compact_blocks_decoded + " s=" + $c.seconds) }
    foreach ($l in $v.lineage.links) { Write-Output ("  lineage parent count=" + $l.count + " physical_pin=" + $l.parent_physical_pin) }
}
