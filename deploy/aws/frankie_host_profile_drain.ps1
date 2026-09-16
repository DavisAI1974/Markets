$ErrorActionPreference = 'Stop'
# Profile one read-only drain of the cycle-1 compact prefix (single thread, then 15 workers) and of the
# cycle-0 raw prefix, with the repository's own readers. Reports land in E:\bench\profile_*.json.
$py = 'E:\Codex\Frankie-BOSS-20260915\actual-host-python\Scripts\python.exe'
$tool = 'C:\tools\Markets\research\kalshi\frankie_boss\operations\profile_journal_drain.py'
New-Item -ItemType Directory -Force E:\bench | Out-Null
$env:PYTHONDONTWRITEBYTECODE = '1'
Push-Location E:\Codex\Frankie-BOSS-20260915\sunday-launch-20260915\Markets
& $py $tool --journal E:\Codex\Frankie-BOSS-20260915\actual-prefixes\prefix-01.sqlite `
    --receipt E:\Codex\Frankie-BOSS-20260915\actual-prefixes\prefix-01-receipt.json `
    --workers 15 --top 18 --report E:\bench\profile_prefix01_compact.json
& $py $tool --journal E:\Codex\Frankie-BOSS-20260915\source-execution-20260915\actual-first-cutoff-capacity\prefix.sqlite `
    --receipt E:\Codex\Frankie-BOSS-20260915\source-execution-20260915\actual-first-cutoff-capacity\prefix-receipt.json `
    --top 18 --report E:\bench\profile_prefix00_raw.json
Pop-Location
